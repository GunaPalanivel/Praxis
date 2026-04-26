from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
FIGURES_DIR = DOCS_DIR / "figures"
CHECKPOINT_DIR = ROOT / "checkpoints" / "praxis-grpo"


def _extract_rewards(log_path: Path) -> list[float]:
    rewards: list[float] = []
    line_pattern = re.compile(r"^\[STEP\].*reward=([0-9]*\.?[0-9]+)")
    for line in log_path.read_text(encoding="utf-8").splitlines():
        match = line_pattern.search(line.strip())
        if match:
            rewards.append(float(match.group(1)))
    return rewards


def _load_training_metrics(csv_path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                {
                    "reward": float(row.get("reward", "0") or 0.0),
                    "loss": float(row.get("loss", "0") or 0.0),
                }
            )
    return rows


def _save_rollout_compare(
    baseline_rewards: list[float], trained_rewards: list[float]
) -> Path:
    max_len = max(len(baseline_rewards), len(trained_rewards))
    if max_len == 0:
        raise RuntimeError("Cannot plot rollout comparison without rewards.")

    x = np.arange(1, max_len + 1)
    baseline = np.array(baseline_rewards + [np.nan] * (max_len - len(baseline_rewards)))
    trained = np.array(trained_rewards + [np.nan] * (max_len - len(trained_rewards)))

    plt.figure(figsize=(10, 5))
    plt.plot(x, baseline, color="red", linewidth=2, label="Untrained Baseline")
    plt.plot(x, trained, color="green", linewidth=2, label="Trained Agent")
    plt.xlabel("Inference step index (from rollout logs)")
    plt.ylabel("Per-step reward")
    plt.title("Praxis Rollout Comparison: Baseline vs Trained (inference logs)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FIGURES_DIR / "rollout_compare.png"
    plt.savefig(out_path, dpi=150)
    plt.close()
    return out_path


def _save_training_evolution_md(
    *,
    baseline_rewards: list[float],
    trained_rewards: list[float],
    training_metrics: list[dict[str, float]],
    manifest: dict,
) -> Path:
    baseline_mean = float(np.mean(baseline_rewards)) if baseline_rewards else 0.0
    trained_mean = float(np.mean(trained_rewards)) if trained_rewards else 0.0
    lift = (trained_mean / baseline_mean) if baseline_mean > 0 else 0.0

    metric_rewards = [m["reward"] for m in training_metrics]
    metric_losses = [m["loss"] for m in training_metrics]
    first_reward = metric_rewards[0] if metric_rewards else 0.0
    last_reward = metric_rewards[-1] if metric_rewards else 0.0
    first_loss = metric_losses[0] if metric_losses else 0.0
    last_loss = metric_losses[-1] if metric_losses else 0.0

    lines = [
        "# Training Evolution Log",
        "",
        f"- Run name: `{manifest.get('run_name', 'unknown')}`",
        f"- Created at: `{manifest.get('created_at', 'unknown')}`",
        f"- Model: `{manifest.get('model', 'unknown')}`",
        f"- Tasks: `{', '.join(manifest.get('tasks', []))}`",
        f"- Seed: `{manifest.get('seed', 'unknown')}`",
        "",
        "## Rollout Comparison",
        "",
        f"- Baseline mean reward: `{baseline_mean:.6f}`",
        f"- Trained mean reward: `{trained_mean:.6f}`",
        f"- Reward lift (trained / baseline): `{lift:.4f}x`",
        "",
        "## Training-Metrics Progression",
        "",
        f"- Logged points: `{len(training_metrics)}`",
        f"- Reward progression: `{first_reward:.6f} -> {last_reward:.6f}`",
        f"- Loss progression: `{first_loss:.6f} -> {last_loss:.6f}`",
        "",
        "## Evidence Files",
        "",
        "- `docs/rollout_baseline.txt`",
        "- `docs/rollout_trained.txt`",
        "- `docs/figures/rollout_compare.png`",
        "- `checkpoints/praxis-grpo/run_manifest.json`",
        "- `checkpoints/praxis-grpo/metrics.csv`",
    ]

    out_path = DOCS_DIR / "training_evolution.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def main() -> None:
    baseline_log = DOCS_DIR / "rollout_baseline.txt"
    trained_log = DOCS_DIR / "rollout_trained.txt"
    metrics_csv = CHECKPOINT_DIR / "metrics.csv"
    manifest_path = CHECKPOINT_DIR / "run_manifest.json"

    if not baseline_log.exists() or not trained_log.exists():
        raise FileNotFoundError("Missing rollout logs in docs/.")
    if not metrics_csv.exists() or not manifest_path.exists():
        raise FileNotFoundError(
            "Missing checkpoint artifacts in checkpoints/praxis-grpo/."
        )

    baseline_rewards = _extract_rewards(baseline_log)
    trained_rewards = _extract_rewards(trained_log)
    training_metrics = _load_training_metrics(metrics_csv)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    compare_path = _save_rollout_compare(baseline_rewards, trained_rewards)
    evolution_path = _save_training_evolution_md(
        baseline_rewards=baseline_rewards,
        trained_rewards=trained_rewards,
        training_metrics=training_metrics,
        manifest=manifest,
    )

    print(f"Saved {compare_path.as_posix()}")
    print(f"Saved {evolution_path.as_posix()}")


if __name__ == "__main__":
    main()
