#!/usr/bin/env python3
"""Push the Space runtime bundle from a git ref to Hugging Face Space gp5901/praxis.

Uses the same file set as ``Dockerfile`` (runtime only), taken from ``git archive``
so the Hub Space matches a chosen branch (default: ``origin/main``).

Auth: ``HF_TOKEN`` (recommended in CI) or an existing ``hf auth login`` session.

Examples::

    uv run python scripts/sync_hf_praxis_space.py --dry-run
    HF_TOKEN=hf_... uv run python scripts/sync_hf_praxis_space.py
    uv run python scripts/sync_hf_praxis_space.py --ref origin/fix/production-merge-gap
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

# Paths copied in Dockerfile + Space-facing docs (Blog.MD is linked from README).
SPACE_PATHS: tuple[str, ...] = (
    "Dockerfile",
    "README.md",
    "Blog.MD",
    "openenv.yaml",
    "LICENSE-3rd-party",
    "pyproject.toml",
    "praxis_env",
    "server",
    "data",
    "inference.py",
)


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        sys.stderr.write(r.stderr or r.stdout or "")
        raise subprocess.CalledProcessError(r.returncode, ["git", *args])
    return (r.stdout or "").strip()


def _resolve_ref(repo: Path, ref: str) -> str:
    """Return fully qualified ref or SHA for git archive."""
    try:
        return _git(repo, "rev-parse", "--verify", ref)
    except subprocess.CalledProcessError:
        pass
    # e.g. user passed "main" without fetching
    _git(
        repo,
        "fetch",
        "origin",
        ref.split("/")[-1] if "/" not in ref else ref,
        "--depth",
        "1",
    )
    return _git(repo, "rev-parse", "--verify", ref)


def _export_tree(repo: Path, treeish: str, dest: Path) -> None:
    out = subprocess.check_output(
        ["git", "archive", "--format=tar", treeish, *SPACE_PATHS],
        cwd=repo,
    )
    with tarfile.open(fileobj=io.BytesIO(out), mode="r:") as tf:
        # filter= requires Python 3.12+
        if sys.version_info >= (3, 12):
            tf.extractall(dest, filter="data")
        else:
            tf.extractall(dest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Git checkout of Praxis (default: repo root)",
    )
    parser.add_argument(
        "--ref",
        default="origin/main",
        help="Tree-ish to export (default: origin/main)",
    )
    parser.add_argument(
        "--space",
        default="gp5901/praxis",
        help="HF Space repo id (default: gp5901/praxis)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("HF_TOKEN"),
        help="HF access token (default: env HF_TOKEN; else hf CLI login)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print resolved SHA and paths; do not upload",
    )
    args = parser.parse_args()
    repo: Path = args.repo_root
    if not (repo / ".git").is_dir():
        print("error: --repo-root must be a git checkout", file=sys.stderr)
        return 2

    sha = _resolve_ref(repo, args.ref)
    print(f"Export ref {args.ref!r} -> {sha}")

    if args.dry_run:
        print("Dry run: would upload these paths from archive:")
        for p in SPACE_PATHS:
            print(f"  {p}")
        print(f"hf upload {args.space} <staging> . --repo-type space ...")
        return 0

    with tempfile.TemporaryDirectory(prefix="praxis-hf-space-") as tmp:
        staging = Path(tmp)
        _export_tree(repo, sha, staging)
        cmd = [
            "hf",
            "upload",
            args.space,
            str(staging),
            ".",
            "--repo-type",
            "space",
            "--commit-message",
            f"sync space from git {sha[:12]} ({args.ref})",
        ]
        if args.token:
            cmd.extend(["--token", args.token])
        print("Running:", " ".join(cmd[:6]), "...")
        subprocess.run(cmd, check=True)
    print("Done:", f"https://huggingface.co/spaces/{args.space}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
