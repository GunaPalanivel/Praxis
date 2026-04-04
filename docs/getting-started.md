# Getting Started

Get Praxis running and call your first episode in under 5 minutes.

## Prerequisites

- Python 3.11+
- Docker (for containerized deployment)
- An OpenAI-compatible API key (HuggingFace token for HF inference)

---

## Option 1: Run Locally (Development)

```bash
# 1. Clone the repo
git clone https://github.com/your-org/praxis-env
cd praxis-env

# 2. Install
pip install -e ".[dev]"

# 3. Start the server
python -m uvicorn server.app:app --host 0.0.0.0 --port 7860

# 4. Verify it's running
curl http://localhost:7860/health
```

Expected response:
```json
{
  "status": "ok",
  "environment": "praxis-env",
  "version": "1.0.0",
  "available_tasks": ["single-service-alert", "cascading-failure", "ambiguous-incident"]
}
```

---

## Option 2: Run with Docker

```bash
# Build the image
docker build -t praxis-env .

# Run the container
docker run -p 7860:7860 praxis-env

# Verify
curl http://localhost:7860/health
```

---

## Your First Episode

Once the server is running, interact with it using any HTTP client:

```python
import httpx

base = "http://localhost:7860"

# 1. Start an episode
obs = httpx.post(f"{base}/reset", json={"task_name": "single-service-alert"}).json()
print(obs["alert_summary"])
# → 🚨 INCIDENT ALERT: AUTH-001 — Auth service error rate elevated

# 2. Investigate
result = httpx.post(f"{base}/step", json={"command": "query_logs service=auth timerange=5m"}).json()
print(result["observation"]["investigation_result"])
# → 14:27:01 [ERROR] Connection refused: postgres://db.internal:5432/auhdb
# → ...

print(f"Reward: {result['reward']}")  # → 0.05

# 3. Diagnose
result = httpx.post(f"{base}/step", json={"command": "diagnose root_cause=bad_config"}).json()
print(result["reward"])   # → 0.20

# 4. Remediate
result = httpx.post(f"{base}/step", json={"command": "rollback_deploy service=auth"}).json()
print(result["done"])     # → True
print(result["reward"])   # → 0.25
```

---

## Running the Baseline Agent

The included `inference.py` runs a full agentic loop against all 3 tasks:

```bash
export HF_TOKEN=hf_your_token_here
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct

python inference.py
```

Output follows the OpenEnv stdout contract:
```
[START] task=single-service-alert env=praxis model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action=query_logs service=auth timerange=5m reward=0.05 done=false error=null
[STEP] step=2 action=check_metrics service=auth metric=error_rate reward=0.05 done=false error=null
...
[END] success=true steps=5 rewards=0.05,0.05,0.05,0.20,0.25
```

---

## Available Tasks

| Task | Difficulty | What the Agent Must Do |
|---|---|---|
| `single-service-alert` | Easy | Diagnose a bad config, rollback deploy |
| `cascading-failure` | Medium | Find root cause in a multi-service cascade |
| `ambiguous-incident` | Hard | Correlate across 4+ services, identify DNS root cause |

See [Tasks & Difficulty](./tasks.md) for full details.

---

## Next Steps

- Read the [Action Space](./action-space.md) to understand every command available
- Read the [Reward Function](./reward-function.md) to understand how scoring works
- Read [Contributing](./contributing.md) to add your own scenarios
