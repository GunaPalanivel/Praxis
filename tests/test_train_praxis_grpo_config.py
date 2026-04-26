"""Fast unit tests for GRPO trainer CLI and dataset construction (no TRL / GPU)."""

import sys

import pytest

from train_praxis_grpo import _build_training_rows, parse_args


def test_default_learning_rate_and_wandb_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["train_praxis_grpo.py"])
    args = parse_args()
    assert args.learning_rate == pytest.approx(1e-4)
    assert args.no_wandb is False


def test_cli_learning_rate_and_no_wandb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train_praxis_grpo.py",
            "--learning-rate",
            "0.0002",
            "--no-wandb",
            "--smoke",
        ],
    )
    args = parse_args()
    assert args.learning_rate == pytest.approx(2e-4)
    assert args.no_wandb is True
    assert args.smoke is True


def test_build_training_rows_repeats() -> None:
    rows = _build_training_rows(["single-service-alert", "cascading-failure"], 3)
    assert len(rows) == 6
    assert {r["task_name"] for r in rows} == {
        "single-service-alert",
        "cascading-failure",
    }
    from collections import Counter

    tasks = Counter(r["task_name"] for r in rows)
    assert tasks["single-service-alert"] == 3
    assert tasks["cascading-failure"] == 3
    assert all("single-service-alert" in r["prompt"] or "cascading" in r["prompt"] for r in rows)
