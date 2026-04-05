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

## Run with Docker

Build and run from the repository root:

```bash
docker build -t praxis-env:latest .
docker run --rm -p 7860:7860 --name praxis-env praxis-env:latest
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
pytest tests/test_task1_single_service_alert.py tests/test_task2_cascading_failure.py tests/test_task3_ambiguous_incident.py -v
```

Contract-focused baseline inference tests:

```bash
pytest tests/test_inference.py -v
```

---

## Run baseline inference

With the server running:

```bash
python inference.py
```

This emits strict one-line records for each task:

```text
[START] task=<task_name> env=praxis model=<model_name>
[STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
[END] success=<true|false> steps=<n> rewards=<r1,r2,...,rn>
```

---

## Current repo boundaries

The current repository includes the baseline inference script, test suite, and
root Dockerfile for deployment.

---

## Next steps

- Read [Tasks](./tasks.md) for the current scenario catalog
- Read [API Reference](./api-reference.md) for the live endpoint contract
- Read [Contributing](./contributing.md) if you want to extend the environment
