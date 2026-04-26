#!/usr/bin/env python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "huggingface_hub>=0.27.0",
# ]
# ///
"""HF Jobs bootstrap for the Praxis full GRPO training run.

This script is designed to be invoked by ``hf jobs uv run`` from a *raw*
GitHub URL pinned at a specific commit SHA, so the launcher and the trainer
source ride on the same revision and judges can reproduce the run byte-for-
byte. See ``scripts/submit_hf_grpo_job.py`` for the submitter side.

Workflow inside the GPU container:

1. Validate required env vars (PRAXIS_COMMIT, HF_TOKEN).
2. ``git clone`` the Praxis repo at the pinned SHA into a workspace dir.
   We deliberately use ``git`` over ``snapshot_download`` because the source
   of truth for this run is GitHub, not the Hub.
3. Invoke ``uv run train_praxis_grpo.py`` so the trainer's own PEP 723
   header (``trl``, ``transformers``, ``unsloth``, ``trackio`` ...) is the
   single dependency declaration we have to keep current.
4. Upload ``checkpoints/praxis-grpo/`` (manifest + metrics) to the Hub model
   repo so the run is permanently attached to the artifact judges grade.

All knobs are env vars so the submitter side stays declarative; defaults
match the production-merge issue (lr=1e-4, group_size=8, 200 episodes).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"[bootstrap] FATAL: required env var {name} is not set", flush=True)
        sys.exit(2)
    return value


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _run(cmd: list[str], *, cwd: str | None = None, check: bool = True) -> int:
    print(f"[bootstrap] $ {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=cwd, check=False)
    if check and result.returncode != 0:
        print(f"[bootstrap] FATAL: command exited {result.returncode}", flush=True)
        sys.exit(result.returncode)
    return result.returncode


def main() -> int:
    started = time.time()
    print(f"[bootstrap] Praxis GRPO launcher starting at t={started:.0f}", flush=True)

    commit = _require_env("PRAXIS_COMMIT")
    _require_env("HF_TOKEN")

    repo_url = _env("PRAXIS_REPO", "https://github.com/GunaPalanivel/Praxis.git")
    base_url = _env("PRAXIS_BASE_URL", "https://gp5901-praxis.hf.space")
    model_alias = _env("PRAXIS_MODEL", "qwen-7b")
    steps = _env("PRAXIS_STEPS", "200")
    lr = _env("PRAXIS_LR", "1e-4")
    group_size = _env("PRAXIS_GROUP_SIZE", "8")
    tasks = _env(
        "PRAXIS_TASKS",
        "single-service-alert,ambiguous-incident,cascading-failure,memory-leak",
    )
    max_turns = _env("PRAXIS_MAX_TURNS", "150")
    seed = _env("PRAXIS_SEED", "2026")
    workdir = Path(_env("PRAXIS_WORKDIR", "/tmp/praxis-grpo"))

    hub_model_id = _env("HF_HUB_MODEL_ID", "")
    trackio_space = _env("TRACKIO_SPACE_ID", "")

    print("[bootstrap] resolved config:", flush=True)
    for k, v in {
        "PRAXIS_REPO": repo_url,
        "PRAXIS_COMMIT": commit,
        "PRAXIS_BASE_URL": base_url,
        "PRAXIS_MODEL": model_alias,
        "PRAXIS_STEPS": steps,
        "PRAXIS_LR": lr,
        "PRAXIS_GROUP_SIZE": group_size,
        "PRAXIS_TASKS": tasks,
        "PRAXIS_MAX_TURNS": max_turns,
        "PRAXIS_SEED": seed,
        "PRAXIS_WORKDIR": str(workdir),
        "HF_HUB_MODEL_ID": hub_model_id or "(unset; checkpoints stay in container)",
        "TRACKIO_SPACE_ID": trackio_space or "(unset; trackio local-only)",
    }.items():
        print(f"  {k}={v}", flush=True)

    if workdir.exists():
        print(f"[bootstrap] cleaning stale workdir {workdir}", flush=True)
        shutil.rmtree(workdir)
    workdir.parent.mkdir(parents=True, exist_ok=True)

    _run(["git", "clone", "--filter=blob:none", "--no-tags", repo_url, str(workdir)])
    _run(["git", "-C", str(workdir), "fetch", "--depth", "1", "origin", commit])
    _run(["git", "-C", str(workdir), "checkout", "--detach", commit])

    head_sha = subprocess.check_output(
        ["git", "-C", str(workdir), "rev-parse", "HEAD"], text=True
    ).strip()
    if head_sha != commit:
        print(
            f"[bootstrap] FATAL: HEAD={head_sha} != requested commit={commit}",
            flush=True,
        )
        return 3
    print(f"[bootstrap] checkout verified at {head_sha}", flush=True)

    trainer_env = os.environ.copy()
    trainer_env["PRAXIS_URL"] = base_url
    trainer_env.setdefault("PRAXIS_BASE_URL", base_url)
    trainer_env.setdefault("PYTHONUNBUFFERED", "1")

    train_cmd = [
        "uv",
        "run",
        "train_praxis_grpo.py",
        "--steps",
        steps,
        "--learning-rate",
        lr,
        "--group-size",
        group_size,
        "--tasks",
        tasks,
        "--model",
        model_alias,
        "--max-turns",
        max_turns,
        "--seed",
        seed,
        "--base-url",
        base_url,
    ]
    print(f"[bootstrap] $ {' '.join(train_cmd)}", flush=True)
    train_proc = subprocess.run(
        train_cmd, cwd=str(workdir), env=trainer_env, check=False
    )
    train_rc = train_proc.returncode
    if train_rc != 0:
        print(
            f"[bootstrap] WARN: trainer exited {train_rc}; will still try to upload partial artifacts",
            flush=True,
        )

    artifacts_dir = workdir / "checkpoints" / "praxis-grpo"
    if hub_model_id and artifacts_dir.exists() and any(artifacts_dir.iterdir()):
        try:
            from huggingface_hub import HfApi

            print(
                f"[bootstrap] uploading {artifacts_dir} to {hub_model_id} (folder=checkpoints/praxis-grpo)",
                flush=True,
            )
            api = HfApi()
            api.create_repo(repo_id=hub_model_id, repo_type="model", exist_ok=True)
            api.upload_folder(
                folder_path=str(artifacts_dir),
                path_in_repo="checkpoints/praxis-grpo",
                repo_id=hub_model_id,
                repo_type="model",
                commit_message=f"Praxis GRPO run @ {commit[:8]}",
            )
            print(
                f"[bootstrap] hub_artifacts=https://huggingface.co/{hub_model_id}/tree/main/checkpoints/praxis-grpo",
                flush=True,
            )
        except Exception as exc:
            print(f"[bootstrap] WARN: artifact upload failed: {exc!r}", flush=True)
    elif not hub_model_id:
        print(
            "[bootstrap] HF_HUB_MODEL_ID unset; skipping artifact upload (set it to persist run_manifest.json + metrics.csv)",
            flush=True,
        )
    else:
        print(
            f"[bootstrap] WARN: artifacts dir {artifacts_dir} missing or empty; nothing to upload",
            flush=True,
        )

    elapsed = time.time() - started
    print(
        f"[bootstrap] done in {elapsed:.0f}s (trainer_rc={train_rc}, sha={commit[:8]})",
        flush=True,
    )
    return train_rc


if __name__ == "__main__":
    sys.exit(main())
