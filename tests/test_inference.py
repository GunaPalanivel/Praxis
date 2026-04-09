"""
tests/test_inference.py - Phase 7 output contract tests.

Focuses on pure formatting and command-selection helpers so tests are
deterministic and do not require network access.
"""

from __future__ import annotations

import re

import inference


def test_render_start_line_contract():
    line = inference.render_start_line(
        task="single-service-alert",
        env_name="praxis",
        model_name="Qwen/Qwen2.5-72B-Instruct",
    )
    assert (
        line
        == "[START] task=single-service-alert env=praxis model=Qwen/Qwen2.5-72B-Instruct"
    )


def test_render_step_line_contract_two_decimal_and_lowercase_bool():
    line = inference.render_step_line(
        step=2,
        action="query_logs service=auth timerange=5m",
        reward=0.5,
        done=False,
        error=None,
    )
    assert (
        line
        == "[STEP] step=2 action=query_logs service=auth timerange=5m "
        "reward=0.50 done=false error=null"
    )


def test_render_step_line_normalizes_multiline_action_and_error():
    line = inference.render_step_line(
        step=1,
        action="query_logs service=auth\n timerange=5m",
        reward=0.0,
        done=True,
        error="unknown\ncommand",
    )
    assert "\n" not in line
    assert "done=true" in line
    assert "error=unknown command" in line


def test_render_end_line_contract_and_rewards_csv():
    line = inference.render_end_line(
        success=True,
        steps=3,
        rewards=[0.0, 0.05, 0.2],
    )
    assert line == "[END] success=true steps=3 rewards=0.00,0.05,0.20"


def test_render_end_line_allows_empty_rewards_list():
    line = inference.render_end_line(success=False, steps=0, rewards=[])
    assert line == "[END] success=false steps=0 rewards="


def test_parse_task_list_uses_defaults_for_empty_input():
    tasks = inference.parse_task_list(None)
    assert tasks == [
        "single-service-alert",
        "cascading-failure",
        "ambiguous-incident",
        "memory-leak",
    ]


def test_parse_task_list_filters_invalid_tasks():
    tasks = inference.parse_task_list(
        "single-service-alert,not-a-task,cascading-failure"
    )
    assert tasks == ["single-service-alert", "cascading-failure"]


def test_parse_task_list_falls_back_when_all_invalid():
    tasks = inference.parse_task_list("foo,bar")
    assert tasks == [
        "single-service-alert",
        "cascading-failure",
        "ambiguous-incident",
        "memory-leak",
    ]


def test_fallback_command_sequences_start_correctly():
    assert (
        inference.fallback_command("single-service-alert", 1)
        == "query_logs service=auth timerange=5m"
    )
    assert (
        inference.fallback_command("cascading-failure", 1)
        == "query_logs service=api timerange=10m"
    )
    assert (
        inference.fallback_command("ambiguous-incident", 1)
        == "query_logs service=frontend timerange=10m"
    )


def test_fallback_command_clamps_to_last_sequence_item():
    cmd = inference.fallback_command("single-service-alert", 999)
    assert cmd == "rollback_deploy service=auth"


def test_model_output_normalization_keeps_single_command():
    text = "command: query_logs service=auth timerange=5m\nextra text"
    normalized = inference._normalize_model_output(text)
    assert normalized == "query_logs service=auth timerange=5m"


def test_step_line_matches_contract_regex():
    line = inference.render_step_line(
        step=4,
        action="diagnose root_cause=bad_config",
        reward=0.2,
        done=False,
        error=None,
    )
    pattern = re.compile(
        r"^\[STEP\] step=\d+ action=.+ reward=\d+\.\d{2} done=(true|false) error=(.+)$"
    )
    assert pattern.match(line)


def test_emit_step_line_once_emits_on_first_use(capsys):
    emitted: set[int] = set()
    did_emit = inference.emit_step_line_once(
        emitted,
        step=2,
        action="check_deps service=api",
        reward=0.02,
        done=False,
        error=None,
    )

    captured = capsys.readouterr()
    assert did_emit is True
    assert "[STEP] step=2 action=check_deps service=api reward=0.02 done=false error=null" in captured.out
    assert emitted == {2}


def test_emit_step_line_once_skips_duplicate_step(capsys):
    emitted: set[int] = set()
    first = inference.emit_step_line_once(
        emitted,
        step=2,
        action="check_deps service=api",
        reward=0.02,
        done=False,
        error=None,
    )
    second = inference.emit_step_line_once(
        emitted,
        step=2,
        action="check_deps service=api",
        reward=0.02,
        done=False,
        error=None,
    )

    captured = capsys.readouterr()
    assert first is True
    assert second is False
    assert captured.out.count("[STEP] step=2") == 1
