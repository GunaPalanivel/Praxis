from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot Praxis training curves.")
    parser.add_argument(
        "--metrics-csv",
        default="checkpoints/praxis-grpo/metrics.csv",
        help="Path to metrics CSV emitted by train_praxis_grpo.py.",
    )
    parser.add_argument("--out-reward", default="docs/reward_curve.png")
    parser.add_argument("--out-loss", default="docs/loss_curve.png")
    parser.add_argument("--out-rubric", default="docs/rubric_attribution.png")
    return parser.parse_args()


def load_metrics(path: Path) -> dict[str, list[dict[str, float]]]:
    per_task: dict[str, list[dict[str, float]]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            task = row["task"]
            per_task[task].append(
                {
                    "step": float(row["step"]),
                    "reward": float(row["reward"]),
                    "planning": float(row["planning"]),
                    "memory": float(row["memory"]),
                    "recovery": float(row["recovery"]),
                    "terminal": float(row["terminal"]),
                    "loss": float(row["loss"]),
                }
            )
    return per_task


def plot_reward_curve(
    per_task: dict[str, list[dict[str, float]]], out_path: Path
) -> None:
    plt.figure(figsize=(12.8, 7.2))
    for task, rows in sorted(per_task.items()):
        xs = [r["step"] for r in rows]
        ys = [r["reward"] for r in rows]
        plt.plot(xs, ys, marker="o", linewidth=1.5, label=f"trained ({task})")
    if per_task:
        max_step = int(max(rows[-1]["step"] for rows in per_task.values() if rows))
        plt.plot(
            list(range(1, max_step + 1)),
            [0.038] * max_step,
            linestyle="--",
            linewidth=1.5,
            label="random baseline (mean=0.038)",
        )
    plt.title("Praxis Training Reward Curve")
    plt.xlabel("Step")
    plt.ylabel("Reward")
    plt.legend()
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=160)
    plt.close()


def plot_loss_curve(
    per_task: dict[str, list[dict[str, float]]], out_path: Path
) -> None:
    plt.figure(figsize=(12.8, 7.2))
    for task, rows in sorted(per_task.items()):
        xs = [r["step"] for r in rows]
        ys = [r["loss"] for r in rows]
        plt.plot(xs, ys, marker="o", linewidth=1.5, label=task)
    plt.title("Praxis Training Loss Curve")
    plt.xlabel("Step")
    plt.ylabel("Loss")
    plt.legend()
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=160)
    plt.close()


def plot_rubric_attribution(
    per_task: dict[str, list[dict[str, float]]], out_path: Path
) -> None:
    totals = {"planning": 0.0, "memory": 0.0, "recovery": 0.0, "terminal": 0.0}
    count = 0
    for rows in per_task.values():
        for row in rows:
            count += 1
            for key in totals:
                totals[key] += row[key]
    if count == 0:
        means = {key: 0.0 for key in totals}
    else:
        means = {key: value / count for key, value in totals.items()}

    plt.figure(figsize=(12.8, 7.2))
    keys = list(means.keys())
    values = [means[k] for k in keys]
    plt.bar(keys, values)
    plt.title("Per-rubric Mean Attribution")
    plt.xlabel("Rubric")
    plt.ylabel("Mean weighted score")
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=160)
    plt.close()


def main() -> int:
    args = parse_args()
    metrics_path = Path(args.metrics_csv)
    if not metrics_path.is_file():
        raise FileNotFoundError(f"Metrics CSV not found: {metrics_path}")
    per_task = load_metrics(metrics_path)
    plot_reward_curve(per_task, Path(args.out_reward))
    plot_loss_curve(per_task, Path(args.out_loss))
    plot_rubric_attribution(per_task, Path(args.out_rubric))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
