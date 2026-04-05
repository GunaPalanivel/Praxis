# Praxis

Praxis is a Round 1 OpenEnv hackathon submission for the [Meta PyTorch OpenEnv AI Hackathon India 2026.](https://www.scaler.com/school-of-technology/meta-pytorch-hackathon)

It is an incident response environment for training AI agents on production triage, diagnosis, and remediation. The agent interacts with a FastAPI server through a small command language, investigates alerts via logs and metrics, and earns deterministic step rewards for taking the right actions.

## Round 1 Focus

Round 1 asks for a mini RL environment with defined tasks, graders, and reward logic. Praxis is built around that goal:

- deterministic programmatic graders
- three tasks ordered easy -> medium -> hard
- a live OpenEnv-style HTTP API
- a baseline-friendly command surface for agents
- rewards bounded to `[0.0, 1.0]`

LinkedIn post: [Scaler Official announcement](https://www.linkedin.com/posts/scalerofficial_hackathon-scaler-openenvhackathon-activity-7440669004337143808-mncw)

## Current State

This repository currently implements:

- A FastAPI server with `POST /reset`, `POST /step`, `GET /state`, `GET /tasks`, and `GET /health`
- Three deterministic tasks with increasing difficulty
- ASCII-normalized observation text for stable local output
- Centralized per-step reward engine in `server/reward.py`
- Per-step rewards in `[0.0, 1.0]`

## Tasks

| Task                   | Difficulty | Summary                                                            |
| ---------------------- | ---------- | ------------------------------------------------------------------ |
| `single-service-alert` | Easy       | Auth service fails because of a bad deployment config              |
| `cascading-failure`    | Medium     | A runaway analytics query exhausts the database connection pool    |
| `ambiguous-incident`   | Hard       | Intermittent multi-service failures caused by DNS misconfiguration |

## Quick Start

Install dependencies:

```bash
pip install -e ".[dev]"
```

Run the server:

```bash
python -m uvicorn server.app:app --host 0.0.0.0 --port 7860
```

Check the live endpoints:

```bash
curl http://localhost:7860/health
curl http://localhost:7860/tasks
```

Start an episode:

```bash
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_name":"single-service-alert"}'
```

Send a step:

```bash
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{"command":"query_logs service=auth timerange=5m"}'
```

## Baseline Inference

The judge-facing baseline script is at the repository root:

```bash
python inference.py
```

Environment variables:

- `API_BASE_URL` - LLM API endpoint (default: `https://router.huggingface.co/v1`)
- `MODEL_NAME` - model identifier (default: `Qwen/Qwen2.5-72B-Instruct`)
- `HF_TOKEN` - API token used by OpenAI client
- `OPENAI_API_KEY` / `API_KEY` - compatibility fallback if `HF_TOKEN` is not set
- `PRAXIS_URL` - Praxis server URL (default: `http://127.0.0.1:7860`)

The script emits strict stdout records for each task:

```text
[START] task=<task_name> env=praxis model=<model_name>
[STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
[END] success=<true|false> steps=<n> rewards=<r1,r2,...,rn>
```

## Action Space

Supported commands include:

- `query_logs service=<name> timerange=<Nm>`
- `check_metrics service=<name> metric=<type>`
- `check_deps service=<name>`
- `check_config service=<name>`
- `diagnose root_cause=<cause>`
- `restart_service service=<name>`
- `rollback_deploy service=<name>`
- `scale_resource service=<name> resource=<type>`
- `kill_query service=<name> query_id=<id>`
- `escalate reason=<text>`

## Observation Space

Each episode returns a structured observation containing:

- `alert_summary`
- `system_status`
- `investigation_result`
- `available_commands`
- `time_elapsed_minutes`
- `severity`
- `services_affected`
- `step_number`

## Episode State

The `/state` endpoint returns lightweight episode metadata:

- `episode_id`
- `step_count`
- `task_name`
- `incident_resolved`
- `root_cause_identified`
- `cumulative_reward`

## Reward Behavior

Rewards are intentionally sparse but informative:

- Useful investigation commands earn small positive reward
- Correct diagnosis earns a larger reward
- Correct remediation or evidence-backed escalation earns the largest reward
- Wrong diagnosis, wrong remediation, or premature escalation receive no credit
- Rewards are clamped to `[0.0, 1.0]`

## Repository Layout

- `praxis_env/` - public package, client, models, and scenarios
- `server/` - FastAPI app, parser, and environment controller
- `tests/` - import, parser, environment, and task validation tests
- `docs/` - current development documentation
- `idea/` - planning, research, and internal implementation notes

## Notes

- The server is deterministic: the same actions produce the same observations and rewards every run.
- The live task list is available from `GET /tasks`.
- This README reflects the current Round 1 implementation state of the repository.
- For deeper implementation details, see [docs/README.md](docs/README.md).
