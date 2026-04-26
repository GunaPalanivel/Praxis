"""
Local uvicorn autostart for development and smoke tests only.

A managed OpenEnv / multi-tenant host must run the FastAPI app under its own
process manager; do not rely on silent subprocess spawns in production.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx


def _read_log_tail(path: Path, max_bytes: int = 12_000) -> str:
    try:
        raw = path.read_bytes()
        if len(raw) > max_bytes:
            raw = b"...[truncated]\n" + raw[-max_bytes:]
        return raw.decode("utf-8", errors="replace")
    except OSError as exc:
        return f"(could not read log: {exc})"


def _close_stderr_file(proc: subprocess.Popen[Any]) -> None:
    f = getattr(proc, "_praxis_stderr_file", None)
    if f is not None:
        try:
            f.close()
        except OSError:
            pass
        try:
            delattr(proc, "_praxis_stderr_file")
        except Exception:
            pass


def ensure_local_uvicorn(
    base_url: str,
    *,
    start_message: str = "[praxis] Starting local environment server (uvicorn)...",
    healthy_message: str = "[praxis] Server is healthy.",
    timeout_s: float = 15.0,
) -> tuple[subprocess.Popen[Any] | None, Path | None]:
    """
    If ``base_url/health`` is up, return (None, None). Otherwise start
    ``python -m uvicorn server.app:app`` on the port parsed from the URL, with
    stderr going to a temp file. On failure, raises ``RuntimeError`` and embeds
    a tail of the log.

    The caller should ``terminate`` / ``wait`` the process, then call
    ``close_server_process_stderr`` to release the log file handle.
    """
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/health", timeout=1.0)
        if response.status_code == 200:
            return (None, None)
    except Exception:
        pass

    print(start_message, flush=True)
    part = base_url.rstrip("/").rsplit(":", 1)
    if len(part) < 2 or not part[1].isdigit():
        raise RuntimeError(
            f"Cannot parse port from base_url for local server: {base_url!r} "
            "(expected host:port, e.g. http://127.0.0.1:7860)"
        )
    port = part[1]
    log_fd, log_name = tempfile.mkstemp(
        prefix="praxis-uvicorn-",
        suffix=".log",
    )
    os.close(log_fd)
    log_path = Path(log_name)
    log_f = open(log_path, "w", encoding="utf-8", errors="replace", buffering=1)

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "server.app:app",
        "--port",
        port,
        "--host",
        "127.0.0.1",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=log_f,
    )
    try:
        proc._praxis_stderr_file = log_f  # type: ignore[attr-defined]
    except Exception:
        pass
    proc._praxis_stderr_log_path = log_path  # type: ignore[attr-defined]

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc.poll() is not None:
            _close_stderr_file(proc)
            tail = _read_log_tail(log_path)
            msg = (
                f"Uvicorn exited early (code={proc.returncode}). "
                f"Stderr log: {log_path}\n---\n{tail}\n---"
            )
            raise RuntimeError(msg)
        try:
            if httpx.get(f"{base_url.rstrip('/')}/health", timeout=1.0).status_code == 200:
                print(healthy_message, flush=True)
                print(f"[praxis] Server stderr: {log_path}", flush=True)
                return (proc, log_path)
        except Exception:
            time.sleep(0.4)

    _close_stderr_file(proc)
    try:
        proc.terminate()
        proc.wait(timeout=5.0)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    tail = _read_log_tail(log_path)
    raise RuntimeError(
        f"Timed out waiting for {base_url!r} to become healthy. "
        f"Stderr log: {log_path}\n---\n{tail}\n---"
    )


def close_server_process_stderr(proc: subprocess.Popen[Any] | None) -> None:
    if proc is None:
        return
    _close_stderr_file(proc)
