# Getting Started

Get the current Praxis repo running locally and interact with the live server.

---

## Prerequisites

- Python 3.11+
- `pip`

Optional but useful:

- `curl` for quick endpoint checks
- a virtual environment for local development

---

## Install from the repo root

```bash
pip install -e ".[dev]"
```

---

## Start the server

```bash
python -m uvicorn server.app:app --host 0.0.0.0 --port 7860
```

---

## Verify the server

```bash
curl http://localhost:7860/health
curl http://localhost:7860/tasks
```

Expected task output:

```json
{
  "tasks": ["ambiguous-incident", "cascading-failure", "single-service-alert"]
}
```

---

## Run your first episode

```python
import httpx

base = "http://localhost:7860"

obs = httpx.post(
    f"{base}/reset",
    json={"task_name": "single-service-alert"},
).json()

print(obs["alert_summary"])

result = httpx.post(
    f"{base}/step",
    json={"command": "query_logs service=auth timerange=5m"},
).json()

print(result["observation"]["investigation_result"])
print(result["reward"])

result = httpx.post(
    f"{base}/step",
    json={"command": "diagnose root_cause=bad_config"},
).json()

print(result["reward"])

result = httpx.post(
    f"{base}/step",
    json={"command": "rollback_deploy service=auth"},
).json()

print(result["done"])
print(result["reward"])
```

---

## Run the current test suite

```bash
pytest tests/ -v --tb=short
```

Focused validation for the current implemented tasks:

```bash
pytest tests/test_task1_single_service_alert.py tests/test_task2_cascading_failure.py -v
```

---

## Current repo boundaries

The current repository does **not** yet include:

- a root submission `README.md`
- `inference.py`
- Docker packaging

Those are later-phase deliverables. The local development workflow today is the
FastAPI server plus the pytest suite.

---

## Next steps

- Read [Tasks](./tasks.md) for the current scenario catalog
- Read [API Reference](./api-reference.md) for the live endpoint contract
- Read [Contributing](./contributing.md) if you want to extend the environment
