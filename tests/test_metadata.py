from __future__ import annotations

from fastapi.testclient import TestClient

from server.app import app
from server.praxis_environment import PraxisEnvironment


def test_metadata_lists_data_sources_and_rubrics() -> None:
    with TestClient(app) as client:
        response = client.get("/metadata")
        assert response.status_code == 200
        payload = response.json()

    sources = payload.get("data_sources", [])
    assert sources, "/metadata must list at least one data_source"
    source = next((s for s in sources if s["name"] == "praxis-mission-fixtures"), None)
    assert source is not None
    assert source["kind"] == "internal"
    assert source["provenance_prefix"] == "praxis:fixtures"

    rubrics = payload.get("rubrics", [])
    assert {item["name"] for item in rubrics} == {
        "PlanningRubric",
        "MemoryRubric",
        "RecoveryRubric",
        "TerminalRubric",
    }
    assert sum(item["weight"] for item in rubrics) == 1.0


def test_metadata_tasks_match_registered_catalog() -> None:
    with TestClient(app) as client:
        response = client.get("/metadata")
        assert response.status_code == 200
        tasks = {task["name"]: task for task in response.json()["tasks"]}

    assert set(tasks) == set(PraxisEnvironment().list_tasks())
    mission = tasks["cascading-platform-failure"]
    assert mission["difficulty"] == "mission"
    assert mission["max_steps"] == 150
    assert mission["phases"] == [
        "Intake",
        "Exploration",
        "Planning",
        "Execution",
        "Disturbance",
        "Recovery",
        "Completion",
        "Reflection",
    ]


def test_all_tasks_can_reset() -> None:
    with TestClient(app) as client:
        for task_name in PraxisEnvironment().list_tasks():
            response = client.post("/reset", json={"task_name": task_name})
            assert response.status_code == 200, task_name
            payload = response.json()
            assert payload.get("session_id")
            assert payload["observation"]["step_number"] == 0
