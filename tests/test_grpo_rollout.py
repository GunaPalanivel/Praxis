"""Unit tests for GRPO rollout command parsing in ``train_praxis_grpo``."""

from train_praxis_grpo import _commands_for_rollout


def test_one_valid_line() -> None:
    c = _commands_for_rollout(
        "query_logs service=auth timerange=5m",
        "single-service-alert",
        seed=1,
    )
    assert len(c) == 1
    assert "query_logs" in c[0]


def test_multiline_respects_order() -> None:
    c = _commands_for_rollout(
        "query_logs service=auth timerange=5m\n"
        "check_config service=auth\n"
        "diagnose root_cause=bad_config",
        "single-service-alert",
        seed=0,
    )
    assert len(c) == 3
    assert c[0].startswith("query_logs")
    assert c[1].startswith("check_config")
    assert "diagnose" in c[2]


def test_empty_falls_back_to_one_command() -> None:
    c = _commands_for_rollout("", "single-service-alert", seed=99)
    assert len(c) >= 1
    assert c[0]
