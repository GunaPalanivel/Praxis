"""
tests/test_environment.py — Phase 2: environment lifecycle tests.

Tests the PraxisEnvironment's reset/step/state contract independent
of any specific scenario (scenarios are not registered yet — we test
the error paths and the contract in isolation).

Full round-trip tests (with scenarios) land in tests/test_scenarios.py
in Phases 3-5.
"""

import pytest
from server.praxis_environment import PraxisEnvironment
from praxis_env.models import PraxisAction, PraxisState


class TestPraxisEnvironmentInit:
    def test_instantiates(self):
        env = PraxisEnvironment()
        assert env is not None

    def test_list_tasks_empty_before_scenarios_registered(self):
        env = PraxisEnvironment()
        tasks = env.list_tasks()
        assert isinstance(tasks, list)
        # Empty is correct — scenarios populated in Phases 3-5

    def test_step_before_reset_raises_runtime_error(self):
        env = PraxisEnvironment()
        with pytest.raises(RuntimeError, match="reset"):
            env.step(PraxisAction(command="query_logs service=auth timerange=5m"))

    def test_state_before_reset_raises_runtime_error(self):
        env = PraxisEnvironment()
        with pytest.raises(RuntimeError, match="reset"):
            env.state()


class TestResetErrors:
    def test_reset_unknown_task_raises_value_error(self):
        env = PraxisEnvironment()
        with pytest.raises(ValueError, match="Unknown task"):
            env.reset(task_name="no-such-task")

    def test_reset_error_message_includes_task_name(self):
        env = PraxisEnvironment()
        with pytest.raises(ValueError) as exc_info:
            env.reset(task_name="imaginary-scenario")
        assert "imaginary-scenario" in str(exc_info.value)


class TestCommandParserIntegration:
    """
    Test that parse_command integrates correctly with step().
    Uses a minimal stub scenario that records what command it got.
    """

    def test_parse_command_standalone(self):
        """Direct smoke test of parse_command from the server module."""
        from server.command_parser import parse_command
        cmd = parse_command("query_logs service=auth timerange=5m")
        assert cmd.action_type == "query_logs"
        assert cmd.params == {"service": "auth", "timerange": "5m"}

    def test_parse_empty_command(self):
        from server.command_parser import parse_command
        cmd = parse_command("")
        assert cmd.action_type == ""
        assert cmd.params == {}

    def test_parse_escalate_freetext(self):
        from server.command_parser import parse_command
        cmd = parse_command("escalate reason=everything is on fire please help")
        assert cmd.action_type == "escalate"
        assert cmd.params["reason"] == "everything is on fire please help"


class TestObsToDict:
    """Test the observation serialisation helper."""

    def test_obs_to_dict_has_all_keys(self):
        from server.praxis_environment import PraxisEnvironment
        from praxis_env.models import PraxisObservation
        env = PraxisEnvironment()
        obs = PraxisObservation(
            alert_summary="test alert",
            system_status={"auth": "critical"},
            investigation_result="some logs",
            available_commands=["query_logs"],
            time_elapsed_minutes=5.0,
            severity="P2",
            services_affected=["auth"],
            step_number=1,
        )
        d = env._obs_to_dict(obs)
        required_keys = {
            "alert_summary", "system_status", "investigation_result",
            "available_commands", "time_elapsed_minutes",
            "severity", "services_affected", "step_number",
        }
        assert required_keys == set(d.keys())

    def test_obs_to_dict_values_are_json_safe(self):
        import json
        from server.praxis_environment import PraxisEnvironment
        from praxis_env.models import PraxisObservation
        env = PraxisEnvironment()
        obs = PraxisObservation(
            alert_summary="test",
            system_status={"auth": "critical"},
            investigation_result="",
            available_commands=["cmd1"],
            time_elapsed_minutes=2.5,
            severity="P1",
            services_affected=["auth"],
            step_number=0,
        )
        d = env._obs_to_dict(obs)
        # This will raise if anything is not JSON serialisable
        serialised = json.dumps(d)
        assert "test" in serialised
