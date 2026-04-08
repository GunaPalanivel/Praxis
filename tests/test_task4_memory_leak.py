import pytest
from praxis_env.models import ParsedCommand
from praxis_env.scenarios.memory_leak_scenario import MemoryLeakScenario

@pytest.fixture
def scenario():
    s = MemoryLeakScenario()
    s.reset("test_ep_4")
    return s

def test_optimal_path(scenario):
    """Test the documented optimal path for the memory leak scenario runs and resolves correctly."""
    # 1. query_logs worker
    out = scenario.step(ParsedCommand(action_type="query_logs", params={"service": "worker"}))
    assert out.reward > 0.0
    assert not out.done

    # 2. check_metrics worker memory
    out = scenario.step(ParsedCommand(action_type="check_metrics", params={"service": "worker", "metric": "memory"}))
    assert out.reward > 0.0
    assert not out.done

    # 3. check_config worker
    out = scenario.step(ParsedCommand(action_type="check_config", params={"service": "worker"}))
    assert out.reward > 0.0
    assert not out.done
    assert "BATCH_SIZE" in out.investigation_result

    # 4. diagnose
    out = scenario.step(ParsedCommand(action_type="diagnose", params={"root_cause": "large_batch_size_oom"}))
    assert out.reward > 0.0
    assert not out.done
    assert scenario._root_cause_identified

    # 5. rollback_deploy worker
    out = scenario.step(ParsedCommand(action_type="rollback_deploy", params={"service": "worker"}))
    assert out.reward > 0.0
    assert out.done
    assert scenario._incident_resolved
