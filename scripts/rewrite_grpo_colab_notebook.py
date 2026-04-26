#!/usr/bin/env python3
"""Rewrite praxis_grpo_colab.ipynb to use train_praxis_grpo.py (TRL/Unsloth path) like HF Jobs."""

from __future__ import annotations

import json
from pathlib import Path


def _src(lines: list[str]) -> list[str]:
    return [ln if ln.endswith("\n") else ln + "\n" for ln in lines]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    nb_path = root / "praxis_grpo_colab.ipynb"

    md_intro = r"""# Praxis GRPO — Judge evidence (canonical `train_praxis_grpo.py`)

This notebook runs the **same Python entrypoint** as production and [HF Jobs](https://huggingface.co/docs/huggingface_hub/main/en/guides/hf_jobs): [`train_praxis_grpo.py`](https://github.com/GunaPalanivel/Praxis/blob/main/train_praxis_grpo.py).

| Mode | When to use | Command shape |
| ---- | ----------- | ------------- |
| **Quick (default)** | CPU or short Colab session; proves HTTP + metrics + plots | `--smoke` with `--steps` / `--smoke-episodes` (hits live Space, no local server) |
| **Full TRL GRPO** | Colab **GPU** (e.g. T4/A100), 30–90+ min first `uv` resolve | Omit `--smoke`; `--steps 200 --learning-rate 1e-4 --group-size 8 --max-turns 150` (matches `scripts/submit_hf_grpo_job.py`) |

**Reward contract (same as repo README):** `reward_func` drives **HTTP** `POST /reset` then `POST /step` against **`https://gp5901-praxis.hf.space`**. Smoke uses deterministic fallback commands per step; full training samples model completions and executes each line as a command up to `--max-turns`.

**Outputs (under `checkpoints/praxis-grpo/` in the cloned repo):** `metrics.csv`, `run_manifest.json` — copied to `/content` for download. Plots are generated from `metrics.csv` (**reward** and **loss** columns; smoke loss is a stable surrogate `max(0, 1-reward)` per trainer code).

Optional: set Colab secrets **`HF_TOKEN`** + env **`TRACKIO_SPACE_ID=gp5901/trackio`** before the run cell to mirror HF-native logging (omit `--no-wandb` then).
"""

    md_flow = r"""## Data flow (canonical training)

```mermaid
flowchart TB
    subgraph Trainer[train_praxis_grpo.py]
        GR[GRPOTrainer TRL]
        RF[reward_func completions]
    end
    subgraph Remote[Hugging Face Space]
        API[FastAPI /reset /step /state]
        ENV[PraxisEnvironment + scenarios]
        RUB[Reward engine]
    end
    GR --> RF
    RF -->|HTTPS JSON| API
    API --> ENV
    ENV --> RUB
    RUB -->|reward info| RF
```

Smoke path skips **GRPOTrainer** but keeps the **same HTTP env + metrics CSV + manifest** so judges still see real rewards from **`gp5901-praxis.hf.space`**.
"""

    cells: list[dict] = [
        {
            "cell_type": "markdown",
            "id": "30324d17",
            "metadata": {"colab_type": "text", "id": "view-in-github"},
            "source": _src(
                [
                    '<a href="https://colab.research.google.com/github/GunaPalanivel/Praxis/blob/main/praxis_grpo_colab.ipynb" target="_parent"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>'
                ]
            ),
        },
        {
            "cell_type": "markdown",
            "id": "colab-badge",
            "metadata": {"id": "colab-badge"},
            "source": _src(["**Open in Colab:** use the badge at the top of this notebook."]),
        },
        {
            "cell_type": "markdown",
            "id": "md-header",
            "metadata": {"id": "md-header"},
            "source": _src([md_intro, "\n", md_flow]),
        },
        {
            "cell_type": "code",
            "id": "cell-install",
            "metadata": {"id": "cell-install"},
            "outputs": [],
            "source": _src(
                [
                    "# Install uv (PEP 723 deps for train_praxis_grpo.py) + plotting",
                    "%pip install -q uv matplotlib pandas",
                ]
            ),
        },
        {
            "cell_type": "code",
            "id": "cell-clone",
            "metadata": {"id": "cell-clone"},
            "outputs": [],
            "source": _src(
                [
                    "# Clone Praxis (same layout HF Jobs checks out at PRAXIS_COMMIT)",
                    "import os, shutil, subprocess, sys",
                    "from pathlib import Path",
                    "",
                    "REPO = Path(\"/content/Praxis\")",
                    "if REPO.exists():",
                    "    shutil.rmtree(REPO, ignore_errors=True)",
                    "subprocess.run(",
                    "    [\"git\", \"clone\", \"--depth\", \"1\", \"https://github.com/GunaPalanivel/Praxis.git\", str(REPO)],",
                    "    check=True,",
                    ")",
                    "os.chdir(REPO)",
                    "print(\"Repo:\", REPO.resolve())",
                    "print(\"Python:\", sys.executable)",
                ]
            ),
        },
        {
            "cell_type": "code",
            "id": "cell-config",
            "metadata": {"id": "cell-config"},
            "outputs": [],
            "source": _src(
                [
                    "# Defaults aligned with train_praxis_grpo.parse_args + scripts/submit_hf_grpo_job.py",
                    "import os",
                    "",
                    "PRAXIS_BASE_URL = os.environ.get(\"PRAXIS_URL\", \"https://gp5901-praxis.hf.space\")",
                    "TASKS_ARG = \"single-service-alert,ambiguous-incident,cascading-failure,memory-leak\"",
                    "SEED = int(os.environ.get(\"PRAXIS_SEED\", \"2026\"))",
                    "# PRAXIS_COLAB_QUICK=1 (default): smoke run, CPU-friendly. Set PRAXIS_COLAB_QUICK=0 on GPU for full TRL GRPO.",
                    "QUICK = os.environ.get(\"PRAXIS_COLAB_QUICK\", \"1\").lower() in (\"1\", \"true\", \"yes\")",
                    "print(\"PRAXIS_BASE_URL:\", PRAXIS_BASE_URL)",
                    "print(\"QUICK (smoke):\", QUICK)",
                ]
            ),
        },
        {
            "cell_type": "code",
            "id": "cell-api",
            "metadata": {"id": "cell-api"},
            "outputs": [],
            "source": _src(
                [
                    "# Health check against the live Space (same URL the trainer uses)",
                    "import requests",
                    "",
                    "r = requests.get(f\"{PRAXIS_BASE_URL.rstrip('/')}/health\", timeout=30)",
                    "r.raise_for_status()",
                    "print(\"Space health:\", r.json())",
                    "print(\"Space is live.\")",
                ]
            ),
        },
        {
            "cell_type": "code",
            "id": "cell-train",
            "metadata": {"id": "cell-train"},
            "outputs": [],
            "source": _src(
                [
                    "# Run canonical trainer via uv (installs PEP 723 stack: trl, unsloth, …)",
                    "import os, shutil, subprocess, sys",
                    "from pathlib import Path",
                    "",
                    "repo = Path.cwd()",
                    "trainer = repo / \"train_praxis_grpo.py\"",
                    "assert trainer.is_file(), f\"Missing {trainer} — run clone cell first\"",
                    "",
                    "env = os.environ.copy()",
                    "env[\"PRAXIS_URL\"] = PRAXIS_BASE_URL",
                    "",
                    "base_cmd = [",
                    "    \"uv\",",
                    "    \"run\",",
                    "    str(trainer),",
                    "    \"--tasks\",",
                    "    TASKS_ARG,",
                    "    \"--learning-rate\",",
                    "    \"1e-4\",",
                    "    \"--group-size\",",
                    "    \"8\",",
                    "    \"--max-turns\",",
                    "    \"150\",",
                    "    \"--model\",",
                    "    \"qwen-7b\",",
                    "    \"--base-url\",",
                    "    PRAXIS_BASE_URL,",
                    "    \"--seed\",",
                    "    str(SEED),",
                    "]",
                    "",
                    "if QUICK:",
                    "    cmd = base_cmd + [\"--smoke\", \"--smoke-episodes\", \"2\", \"--steps\", \"25\", \"--no-wandb\"]",
                    "else:",
                    "    cmd = base_cmd + [\"--steps\", \"200\"]",
                    "",
                    "print(\"$\", \" \".join(cmd))",
                    "rc = subprocess.run(cmd, cwd=str(repo), env=env).returncode",
                    "if rc != 0:",
                    "    raise SystemExit(f\"train_praxis_grpo.py exited {rc}\")",
                    "ck = repo / \"checkpoints\" / \"praxis-grpo\"",
                    "for name in (\"metrics.csv\", \"run_manifest.json\"):",
                    "    p = ck / name",
                    "    if p.is_file():",
                    "        dest = Path(\"/content\") / name",
                    "        shutil.copy(p, dest)",
                    "        print(\"Copied to\", dest)",
                ]
            ),
        },
        {
            "cell_type": "code",
            "id": "cell-save-logs",
            "metadata": {"id": "cell-save-logs"},
            "outputs": [],
            "source": _src(
                [
                    "# Optional: copy full checkpoint dir listing for judges",
                    "import json, shutil",
                    "from pathlib import Path",
                    "",
                    "ck = Path(\"/content/Praxis/checkpoints/praxis-grpo\")",
                    "if (ck / \"run_manifest.json\").is_file():",
                    "    print(json.dumps(json.loads((ck / \"run_manifest.json\").read_text()), indent=2)[:4000])",
                    "else:",
                    "    print(\"No run_manifest.json yet — re-run train cell.\")",
                ]
            ),
        },
        {
            "cell_type": "code",
            "id": "cell-plots",
            "metadata": {"id": "cell-plots"},
            "outputs": [],
            "source": _src(
                [
                    "# Evidence plots from real metrics.csv (reward + loss)",
                    "import matplotlib.pyplot as plt",
                    "import pandas as pd",
                    "from pathlib import Path",
                    "",
                    "csv_path = Path(\"/content/Praxis/checkpoints/praxis-grpo/metrics.csv\")",
                    "if not csv_path.is_file():",
                    "    csv_path = Path(\"/content/metrics.csv\")",
                    "df = pd.read_csv(csv_path)",
                    "df[\"row\"] = range(len(df))",
                    "fig, (ax0, ax1) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)",
                    "ax0.plot(df[\"row\"], pd.to_numeric(df[\"reward\"], errors=\"coerce\"), color=\"#2563eb\", lw=1.2)",
                    "ax0.set_ylabel(\"Reward\")",
                    "ax0.set_title(\"Praxis training — reward (from metrics.csv)\")",
                    "ax1.plot(df[\"row\"], pd.to_numeric(df[\"loss\"], errors=\"coerce\"), color=\"#7c3aed\", lw=1.2)",
                    "ax1.set_ylabel(\"Loss\")",
                    "ax1.set_xlabel(\"Logged row index\")",
                    "plt.tight_layout()",
                    "plt.savefig(\"/content/reward_curve.png\", dpi=150, bbox_inches=\"tight\")",
                    "plt.savefig(\"/content/loss_curve.png\", dpi=150, bbox_inches=\"tight\")",
                    "plt.show()",
                    "print(\"Saved /content/reward_curve.png and /content/loss_curve.png\")",
                ]
            ),
        },
        {
            "cell_type": "code",
            "id": "cell-judge-summary",
            "metadata": {"id": "cell-judge-summary"},
            "outputs": [],
            "source": _src(
                [
                    "# Summary from run_manifest.json (mean reward per task in smoke)",
                    "import json",
                    "from pathlib import Path",
                    "",
                    "p = Path(\"/content/Praxis/checkpoints/praxis-grpo/run_manifest.json\")",
                    "if not p.is_file():",
                    "    p = Path(\"/content/run_manifest.json\")",
                    "if not p.is_file():",
                    "    print(\"No manifest found.\")",
                    "else:",
                    "    m = json.loads(p.read_text(encoding=\"utf-8\"))",
                    "    summ = m.get(\"summary\", {})",
                    "    print(\"Run:\", m.get(\"run_name\"), \"| smoke:\", m.get(\"smoke\"), \"| steps arg:\", m.get(\"steps\"))",
                    "    print(f\"{'Task':<28} {'mean_reward':>12}\")",
                    "    for task, row in sorted(summ.items()):",
                    "        mr = row.get(\"mean_reward\", 0.0)",
                    "        print(f\"{task:<28} {float(mr):12.4f}\")",
                ]
            ),
        },
        {
            "cell_type": "code",
            "id": "cell-download",
            "metadata": {"id": "cell-download"},
            "outputs": [],
            "source": _src(
                [
                    "try:",
                    "    from google.colab import files",
                    "",
                    "    for fname in [",
                    "        \"/content/metrics.csv\",",
                    "        \"/content/run_manifest.json\",",
                    "        \"/content/reward_curve.png\",",
                    "        \"/content/loss_curve.png\",",
                    "    ]:",
                    "        from pathlib import Path",
                    "",
                    "        if Path(fname).is_file():",
                    "            files.download(fname)",
                    "    print(\"Downloaded artifacts (if files exist).\")",
                    "except ImportError:",
                    "    print(\"Not on Colab — artifacts remain under /content and Praxis/checkpoints/\")",
                ]
            ),
        },
    ]

    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "cells": cells,
    }

    nb_path.write_text(json.dumps(nb, indent=1), encoding="utf-8")
    print("Wrote", nb_path, "cells=", len(cells))


if __name__ == "__main__":
    main()
