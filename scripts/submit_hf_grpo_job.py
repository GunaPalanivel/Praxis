#!/usr/bin/env python
"""Preflight + submit the Praxis full GRPO run on HF Jobs.

Mitigates the well-known ``hf jobs uv run`` clone race in three layers:

1. **Feature branch**: we never assume ``origin/main`` already has the SHA;
   we read ``HEAD`` of the local branch and submit *that* SHA.
2. **Pinned commit**: the job receives ``PRAXIS_COMMIT=<full SHA>`` and the
   bootstrap (``scripts/run_hf_grpo_job.py``) does an explicit
   ``git checkout --detach <SHA>`` and aborts if HEAD drifts.
3. **Local preflight**: before submitting we ``git ls-remote`` the remote
   and verify the SHA is reachable. If not, we exit non-zero with a clear
   message instead of submitting a job that will fail to clone.

Usage:
    python scripts/submit_hf_grpo_job.py \
        --hub-model-id gp5901/praxis-grpo-7b \
        --trackio-space-id gp5901/trackio \
        --flavor a10g-large \
        --timeout 5h

The submitter calls the local ``hf`` CLI (``hf jobs uv run``) so an HF login
(``hf auth login`` or ``HF_TOKEN`` in env) is required. The job itself only
needs ``HF_TOKEN`` as a *secret* (see ``--secrets HF_TOKEN``).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_LAUNCHER_PATH = "scripts/run_hf_grpo_job.py"
DEFAULT_RAW_BASE = "https://raw.githubusercontent.com/GunaPalanivel/Praxis"
DEFAULT_REMOTE = "origin"
DEFAULT_FLAVOR = "a10g-large"
DEFAULT_TIMEOUT = "5h"


def _run(cmd: list[str], *, capture: bool = False, check: bool = True) -> str:
    print(f"[submit] $ {' '.join(cmd)}", flush=True)
    if capture:
        result = subprocess.run(cmd, check=False, text=True, capture_output=True)
    else:
        result = subprocess.run(cmd, check=False, text=True)
    if check and result.returncode != 0:
        if capture:
            sys.stderr.write(result.stderr or "")
        sys.exit(result.returncode)
    return (result.stdout or "").strip() if capture else ""


def _resolve_local_head(branch: str | None) -> str:
    ref = branch or "HEAD"
    sha = _run(["git", "rev-parse", ref], capture=True)
    if len(sha) < 40:
        print(f"[submit] FATAL: could not resolve local SHA for {ref!r}", flush=True)
        sys.exit(2)
    return sha


def _preflight_remote_has_sha(remote: str, sha: str, ref_hint: str | None) -> None:
    """Verify <sha> is reachable on <remote>. Mitigates the clone race."""
    print(f"[submit] preflight: ls-remote {remote} for {sha[:12]}...", flush=True)
    candidates: list[str] = []
    if ref_hint:
        candidates.append(ref_hint)
    candidates.extend(
        [sha, f"refs/heads/{ref_hint}" if ref_hint else "", "refs/heads/main"]
    )
    seen: set[str] = set()
    found = False
    for cand in [c for c in candidates if c and c not in seen]:
        seen.add(cand)
        out = _run(
            ["git", "ls-remote", "--exit-code", remote, cand], capture=True, check=False
        )
        for line in out.splitlines():
            head = line.split()[0] if line else ""
            if head == sha:
                print(
                    f"[submit] preflight OK: {sha[:12]} on {remote}/{cand}", flush=True
                )
                found = True
                break
        if found:
            break

    if not found:
        all_refs = _run(["git", "ls-remote", remote], capture=True, check=False)
        if sha in all_refs:
            print(
                f"[submit] preflight OK: {sha[:12]} reachable on {remote} (no exact ref match)",
                flush=True,
            )
            return
        print(
            f"[submit] FATAL: {sha} not present on {remote}.\n"
            f"  Push the branch first:  git push {remote} HEAD\n"
            f"  Then re-run this script.",
            flush=True,
        )
        sys.exit(3)


def _build_launcher_url(args: argparse.Namespace, sha: str) -> str:
    if args.launcher_url:
        return args.launcher_url
    base = args.raw_base.rstrip("/")
    path = args.launcher_path.lstrip("/")
    return f"{base}/{sha}/{path}"


def _build_hf_command(
    args: argparse.Namespace, sha: str, launcher_url: str
) -> list[str]:
    env_pairs: list[tuple[str, str]] = [
        ("PRAXIS_COMMIT", sha),
        ("PRAXIS_BASE_URL", args.base_url),
        ("PRAXIS_MODEL", args.model),
        ("PRAXIS_STEPS", str(args.steps)),
        ("PRAXIS_LR", args.learning_rate),
        ("PRAXIS_GROUP_SIZE", str(args.group_size)),
        ("PRAXIS_TASKS", args.tasks),
        ("PRAXIS_MAX_TURNS", str(args.max_turns)),
        ("PRAXIS_SEED", str(args.seed)),
    ]
    if args.repo_url:
        env_pairs.append(("PRAXIS_REPO", args.repo_url))
    if args.hub_model_id:
        env_pairs.append(("HF_HUB_MODEL_ID", args.hub_model_id))
    if args.trackio_space_id:
        env_pairs.append(("TRACKIO_SPACE_ID", args.trackio_space_id))

    cmd: list[str] = [
        "hf",
        "jobs",
        "uv",
        "run",
        "--flavor",
        args.flavor,
        "--timeout",
        args.timeout,
    ]
    cmd.extend(["--secrets", "HF_TOKEN"])
    for k, v in env_pairs:
        cmd.extend(["--env", f"{k}={v}"])
    if args.namespace:
        cmd.extend(["--namespace", args.namespace])
    if args.detach:
        cmd.append("--detach")
    cmd.append(launcher_url)
    return cmd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--branch", default=None, help="Local branch/ref to submit (default: HEAD)."
    )
    p.add_argument(
        "--remote",
        default=DEFAULT_REMOTE,
        help="Remote name for preflight (default: origin).",
    )
    p.add_argument(
        "--raw-base",
        default=DEFAULT_RAW_BASE,
        help="Base URL for the launcher; full URL becomes <raw-base>/<sha>/<launcher-path>.",
    )
    p.add_argument(
        "--launcher-path",
        default=DEFAULT_LAUNCHER_PATH,
        help="Path inside the repo to the UV bootstrap script.",
    )
    p.add_argument(
        "--launcher-url",
        default=None,
        help="Override the launcher URL entirely (skips raw-base/launcher-path resolution).",
    )
    p.add_argument(
        "--repo-url",
        default=None,
        help="Override PRAXIS_REPO env (default: https://github.com/GunaPalanivel/Praxis.git).",
    )
    p.add_argument("--base-url", default="https://gp5901-praxis.hf.space")
    p.add_argument("--model", default="qwen-7b", choices=("qwen-7b", "qwen-3b"))
    p.add_argument("--steps", type=int, default=200)
    p.add_argument("--learning-rate", default="1e-4")
    p.add_argument("--group-size", type=int, default=8)
    p.add_argument(
        "--tasks",
        default="single-service-alert,ambiguous-incident,cascading-failure,memory-leak",
    )
    p.add_argument("--max-turns", type=int, default=150)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--hub-model-id", default=os.environ.get("HF_HUB_MODEL_ID", ""))
    p.add_argument("--trackio-space-id", default=os.environ.get("TRACKIO_SPACE_ID", ""))
    p.add_argument("--flavor", default=DEFAULT_FLAVOR)
    p.add_argument("--timeout", default=DEFAULT_TIMEOUT)
    p.add_argument("--namespace", default=None)
    p.add_argument(
        "--detach",
        action="store_true",
        help="Submit then return immediately. Default streams logs (recommended for first run).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved hf jobs command and exit without submitting.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if not Path(".git").exists():
        print("[submit] FATAL: must be run from the Praxis repo root.", flush=True)
        return 2

    sha = _resolve_local_head(args.branch)
    print(f"[submit] local HEAD = {sha}", flush=True)
    _preflight_remote_has_sha(args.remote, sha, args.branch)

    launcher_url = _build_launcher_url(args, sha)
    print(f"[submit] launcher_url = {launcher_url}", flush=True)

    cmd = _build_hf_command(args, sha, launcher_url)
    print(f"[submit] resolved command:\n  {' '.join(cmd)}", flush=True)
    if args.dry_run:
        print("[submit] --dry-run: skipping submission.", flush=True)
        return 0

    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())
