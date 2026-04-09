"""
tests/test_models.py — Phase 1 validation: data model tests.

Validates:
  - PraxisAction, PraxisObservation, PraxisState can be imported
  - All models instantiate correctly with correct field types
  - Default values are correct
  - AVAILABLE_COMMANDS, VALID_METRICS constants are populated
  - Models have the expected fields (API contract)
"""

import pytest
from praxis_env.models import (
    AVAILABLE_COMMANDS,
    VALID_METRICS,
    PraxisAction,
    PraxisObservation,
    PraxisState,
)


class TestPraxisAction:
    def test_instantiate(self):
        action = PraxisAction(command="query_logs service=auth timerange=5m")
        assert action.command == "query_logs service=auth timerange=5m"

    def test_command_is_string(self):
        action = PraxisAction(command="diagnose root_cause=bad_config")
        assert isinstance(action.command, str)

    def test_empty_command_allowed(self):
        action = PraxisAction(command="")
        assert action.command == ""


class TestPraxisObservation:
    def _make_obs(self, **kwargs):
        defaults = dict(
            alert_summary="Test alert",
            system_status={"auth": "critical"},
            investigation_result="",
            available_commands=["query_logs service=<name> timerange=<N>m"],
            time_elapsed_minutes=5.0,
            severity="P2",
            services_affected=["auth"],
            step_number=0,
        )
        defaults.update(kwargs)
        return PraxisObservation(**defaults)

    def test_instantiate(self):
        obs = self._make_obs()
        assert obs.alert_summary == "Test alert"
        assert obs.severity == "P2"
        assert obs.step_number == 0

    def test_all_fields_present(self):
        obs = self._make_obs()
        assert hasattr(obs, "alert_summary")
        assert hasattr(obs, "system_status")
        assert hasattr(obs, "investigation_result")
        assert hasattr(obs, "available_commands")
        assert hasattr(obs, "time_elapsed_minutes")
        assert hasattr(obs, "severity")
        assert hasattr(obs, "services_affected")
        assert hasattr(obs, "step_number")

    def test_system_status_is_dict(self):
        obs = self._make_obs(system_status={"auth": "critical", "api": "healthy"})
        assert isinstance(obs.system_status, dict)

    def test_available_commands_is_list(self):
        obs = self._make_obs()
        assert isinstance(obs.available_commands, list)

    def test_services_affected_is_list(self):
        obs = self._make_obs()
        assert isinstance(obs.services_affected, list)


class TestPraxisState:
    def test_instantiate_minimal(self):
        state = PraxisState(
            episode_id="test_1",
            step_count=0,
            task_name="single-service-alert",
        )
        assert state.episode_id == "test_1"
        assert state.step_count == 0
        assert state.task_name == "single-service-alert"

    def test_defaults(self):
        state = PraxisState(
            episode_id="test_1",
            step_count=0,
            task_name="test",
        )
        assert state.incident_resolved is False
        assert state.root_cause_identified is False
        assert state.cumulative_reward == pytest.approx(0.01)

    def test_all_fields_present(self):
        state = PraxisState(
            episode_id="ep_1",
            step_count=5,
            task_name="cascading-failure",
            incident_resolved=True,
            root_cause_identified=True,
            cumulative_reward=0.65,
        )
        assert state.incident_resolved is True
        assert state.root_cause_identified is True
        assert state.cumulative_reward == pytest.approx(0.65)


class TestConstants:
    def test_available_commands_not_empty(self):
        assert len(AVAILABLE_COMMANDS) > 0

    def test_available_commands_are_strings(self):
        for cmd in AVAILABLE_COMMANDS:
            assert isinstance(cmd, str), f"Command {cmd!r} is not a string"

    def test_key_commands_present(self):
        command_strs = " ".join(AVAILABLE_COMMANDS)
        assert "query_logs" in command_strs
        assert "check_metrics" in command_strs
        assert "diagnose" in command_strs
        assert "escalate" in command_strs
        assert "rollback_deploy" in command_strs

    def test_valid_metrics_not_empty(self):
        assert len(VALID_METRICS) > 0

    def test_key_metrics_present(self):
        assert "error_rate" in VALID_METRICS
        assert "latency_p95" in VALID_METRICS
        assert "connections" in VALID_METRICS
