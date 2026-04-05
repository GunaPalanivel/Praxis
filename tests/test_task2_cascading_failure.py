"""
tests/test_task2_cascading_failure.py - Task 2 scenario tests.

Coverage mirrors Task 1:
  1. Optimal path and total reward
  2. Resolution and escalation rules
  3. Red-herring penalties
  4. Determinism across repeated runs
  5. Reward bounds and crash safety for representative commands
"""

import pytest

from server.command_parser import parse_command
from praxis_env.scenarios.cascading_failure import CascadingFailureScenario


def make_scenario() -> CascadingFailureScenario:
    scenario = CascadingFailureScenario()
    scenario.reset(episode_id="test-2")
    return scenario


def step_cmd(scenario: CascadingFailureScenario, cmd_str: str):
    return scenario.step(parse_command(cmd_str))


class TestOptimalPath:
    OPTIMAL_COMMANDS = [
        "query_logs service=api timerange=10m",
        "check_deps service=api",
        "check_metrics service=database metric=connections",
        "query_logs service=database timerange=15m",
        "diagnose root_cause=db_connection_pool_exhausted",
        "kill_query service=database query_id=runaway_analytics",
        "scale_resource service=database resource=connection_pool",
    ]
    EXPECTED_REWARDS = [0.05, 0.05, 0.10, 0.10, 0.20, 0.15, 0.10]

    def test_optimal_path_rewards(self):
        scenario = make_scenario()
        for cmd, expected in zip(self.OPTIMAL_COMMANDS, self.EXPECTED_REWARDS):
            outcome = step_cmd(scenario, cmd)
            assert outcome.reward == pytest.approx(expected, abs=1e-6)

    def test_optimal_path_total_score(self):
        scenario = make_scenario()
        total = sum(step_cmd(scenario, cmd).reward for cmd in self.OPTIMAL_COMMANDS)
        assert total == pytest.approx(0.75, abs=1e-6)

    def test_optimal_path_done_only_after_second_remediation(self):
        scenario = make_scenario()
        for cmd in self.OPTIMAL_COMMANDS[:-1]:
            outcome = step_cmd(scenario, cmd)
        assert outcome.done is False
        assert outcome.incident_resolved is False

        final_outcome = step_cmd(scenario, self.OPTIMAL_COMMANDS[-1])
        assert final_outcome.done is True
        assert final_outcome.incident_resolved is True
        assert final_outcome.root_cause_identified is True


class TestResolutionRules:
    def test_kill_query_alone_does_not_resolve(self):
        scenario = make_scenario()
        outcome = step_cmd(
            scenario,
            "kill_query service=database query_id=runaway_analytics",
        )
        assert outcome.reward == pytest.approx(0.15)
        assert outcome.done is False
        assert outcome.incident_resolved is False

    def test_scale_pool_alone_does_not_resolve(self):
        scenario = make_scenario()
        outcome = step_cmd(
            scenario,
            "scale_resource service=database resource=connection_pool",
        )
        assert outcome.reward == pytest.approx(0.10)
        assert outcome.done is False
        assert outcome.incident_resolved is False

    def test_escalate_with_three_unique_investigations_ends_episode(self):
        scenario = make_scenario()
        step_cmd(scenario, "query_logs service=api timerange=10m")
        step_cmd(scenario, "check_deps service=api")
        step_cmd(scenario, "check_metrics service=database metric=connections")
        outcome = step_cmd(
            scenario,
            "escalate reason=db pool exhausted by analytics query",
        )
        assert outcome.reward == pytest.approx(0.15)
        assert outcome.done is True
        assert outcome.incident_resolved is True

    def test_escalate_without_enough_evidence_is_penalized(self):
        scenario = make_scenario()
        outcome = step_cmd(scenario, "escalate reason=need help")
        assert outcome.reward == pytest.approx(-0.05)
        assert outcome.done is True
        assert outcome.incident_resolved is False


class TestRedHerrings:
    def test_api_deployment_diagnosis_gets_wrong_diagnosis_penalty(self):
        scenario = make_scenario()
        outcome = step_cmd(scenario, "diagnose root_cause=api_deployment")
        assert outcome.reward == pytest.approx(-0.10)
        assert "deployment" in outcome.investigation_result.lower()

    def test_auth_memory_diagnosis_gets_wrong_diagnosis_penalty(self):
        scenario = make_scenario()
        outcome = step_cmd(scenario, "diagnose root_cause=auth_memory")
        assert outcome.reward == pytest.approx(-0.10)
        assert "memory" in outcome.investigation_result.lower()

    def test_restarting_auth_treats_symptom_not_root_cause(self):
        scenario = make_scenario()
        outcome = step_cmd(scenario, "restart_service service=auth")
        assert outcome.reward == pytest.approx(-0.05)
        assert outcome.incident_resolved is False

    def test_rolling_back_api_deploy_does_not_fix_incident(self):
        scenario = make_scenario()
        outcome = step_cmd(scenario, "rollback_deploy service=api")
        assert outcome.reward == pytest.approx(-0.05)
        assert outcome.incident_resolved is False

    def test_red_herring_path_scores_much_lower_than_optimal(self):
        scenario = make_scenario()
        wrong_path = [
            "query_logs service=api timerange=10m",
            "check_config service=api",
            "diagnose root_cause=api_deployment",
            "rollback_deploy service=api",
        ]
        wrong_total = sum(step_cmd(scenario, cmd).reward for cmd in wrong_path)
        assert wrong_total < 0.20
        assert 0.75 - wrong_total >= 0.30


class TestDeterminism:
    COMMANDS = [
        "query_logs service=api timerange=10m",
        "check_deps service=api",
        "check_metrics service=database metric=connections",
        "query_logs service=database timerange=15m",
        "diagnose root_cause=db_connection_pool_exhausted",
        "kill_query service=database query_id=runaway_analytics",
        "scale_resource service=database resource=connection_pool",
    ]

    def _run_once(self) -> list[float]:
        scenario = make_scenario()
        rewards = []
        for cmd in self.COMMANDS:
            outcome = step_cmd(scenario, cmd)
            rewards.append(outcome.reward)
        return rewards

    def test_three_runs_identical(self):
        run_1 = self._run_once()
        run_2 = self._run_once()
        run_3 = self._run_once()
        assert run_1 == run_2 == run_3

    def test_investigation_result_is_ascii_safe(self):
        scenario = make_scenario()
        outcome = step_cmd(scenario, "query_logs service=api timerange=10m")
        assert outcome.investigation_result.isascii()


class TestRewardBounds:
    REPRESENTATIVE_COMMANDS = [
        "query_logs service=api timerange=10m",
        "query_logs service=database timerange=15m",
        "query_logs service=cache timerange=5m",
        "check_metrics service=database metric=connections",
        "check_metrics service=auth metric=memory",
        "check_deps service=api",
        "check_config service=api",
        "diagnose root_cause=db_connection_pool_exhausted",
        "diagnose root_cause=api_deployment",
        "diagnose root_cause=auth_memory",
        "kill_query service=database query_id=runaway_analytics",
        "kill_query service=database query_id=wrong_query",
        "scale_resource service=database resource=connection_pool",
        "restart_service service=auth",
        "rollback_deploy service=api",
        "escalate reason=need help",
        "",
        "unknown command",
    ]

    @pytest.mark.parametrize("cmd", REPRESENTATIVE_COMMANDS)
    def test_reward_in_bounds(self, cmd):
        scenario = make_scenario()
        outcome = step_cmd(scenario, cmd)
        assert -1.0 <= outcome.reward <= 1.0

    @pytest.mark.parametrize("cmd", REPRESENTATIVE_COMMANDS)
    def test_never_raises(self, cmd):
        scenario = make_scenario()
        try:
            step_cmd(scenario, cmd)
        except Exception as exc:  # pragma: no cover - explicit failure message
            pytest.fail(f"step() raised {type(exc).__name__} for cmd={cmd!r}: {exc}")


class TestRegistration:
    def test_task_is_registered(self):
        from praxis_env.scenarios import list_tasks

        assert "cascading-failure" in list_tasks()

    def test_get_scenario_returns_correct_type(self):
        from praxis_env.scenarios import get_scenario

        scenario = get_scenario("cascading-failure")
        assert isinstance(scenario, CascadingFailureScenario)

    def test_scenario_metadata_is_correct(self):
        assert CascadingFailureScenario.NAME == "cascading-failure"
        assert CascadingFailureScenario.SEVERITY == "P1"
