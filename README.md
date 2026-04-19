---
title: Praxis
emoji: 🔥
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
tags:
  - openenv
pinned: false
---

# Praxis: Production Incident Response Training for AI Agents

Praxis is an OpenEnv-compatible environment that trains and evaluates agents on real-world SRE incident response.
Agents investigate logs and metrics, diagnose root causes, and execute remediations through a command-driven API.

> Built for [Meta PyTorch OpenEnv Hackathon x SST](https://www.scaler.com/school-of-technology/meta-pytorch-hackathon)

## Why This Matters

Incident response is a real production workflow, not a toy benchmark. On-call engineers repeatedly perform triage,
evidence gathering, diagnosis, and remediation under time pressure. Praxis models that workflow with deterministic tasks
and programmatic graders so agent progress can be measured reliably.

The evaluation design targets practical utility: four escalating tasks, reward shaping over the trajectory, and clear
success criteria. This gives useful signal for both training and model comparison while remaining reproducible for
judging and regression testing.

## Quick Start (5 Commands)

```bash
git clone https://github.com/GunaPalanivel/Praxis.git
cd Praxis
pip install -e ".[dev]"
python -m uvicorn server.app:app --host 0.0.0.0 --port 7860
curl http://localhost:7860/health
```

Optional smoke checks:

```bash
curl http://localhost:7860/tasks
curl -X POST http://localhost:7860/reset
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" -d '{}'
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" -d '{"task_name":"single-service-alert"}'
curl -X POST http://localhost:7860/step -H "Content-Type: application/json" -d '{"command":"query_logs service=auth timerange=5m"}'
```

## Environment Overview

### Action Space

The agent sends one text command per step.

| Command Template                                | Purpose                                                     |
| ----------------------------------------------- | ----------------------------------------------------------- |
| `query_logs service=<name> timerange=<N>m`      | Inspect service logs over a time window                     |
| `check_metrics service=<name> metric=<type>`    | Read service or infrastructure metrics                      |
| `check_deps service=<name>`                     | Inspect dependency graph for a service                      |
| `check_config service=<name>`                   | Inspect recent config and deployment changes                |
| `check_runbook service=<name>`                  | Access institutional SRE runbooks for triage guidance       |
| `diagnose root_cause=<cause>`                   | Declare the suspected root cause                            |
| `restart_service service=<name>`                | Restart a service as remediation                            |
| `rollback_deploy service=<name>`                | Roll back a recent deploy                                   |
| `scale_resource service=<name> resource=<type>` | Increase/adjust capacity (task dependent)                   |
| `kill_query service=<name> query_id=<id>`       | Stop a runaway query                                        |
| `escalate reason=<text>`                        | Escalate with evidence when direct remediation is not ideal |

Valid metric examples include `error_rate`, `latency_p95`, `connections`, `memory`, `cpu`, and `resolution_failures`.

### Observation Space

Each `reset` and `step` returns a `PraxisObservation` payload with these fields:

| Field                  | Type               | Meaning                                                        |
| ---------------------- | ------------------ | -------------------------------------------------------------- |
| `alert_summary`        | string             | Current incident summary                                       |
| `system_status`        | map<string,string> | Service health map (`healthy`, `degraded`, `critical`, `down`) |
| `investigation_result` | string             | Result of the latest action                                    |
| `available_commands`   | list<string>       | Command templates the agent can issue                          |
| `time_elapsed_minutes` | float              | Incident time progression (2.5 minutes per step)               |
| `severity`             | string             | Incident severity (`P0`, `P1`, `P2`, `P3`)                     |
| `services_affected`    | list<string>       | Services currently not healthy                                 |
| `step_number`          | int                | Current step index                                             |

Text fields are ASCII-normalized for stable local console output.

### Episode State

`GET /state` returns compact state metadata:

- `episode_id`
- `step_count`
- `task_name`
- `incident_resolved`
- `root_cause_identified`
- `cumulative_reward`

Praxis is deterministic: the same action sequence yields the same outputs and rewards.

## Tasks

| Task                   | Difficulty | Severity | Max Steps | Scenario Summary                                                          | Optimal Path Score |
| ---------------------- | ---------- | -------- | --------- | ------------------------------------------------------------------------- | ------------------ |
| `single-service-alert` | Easy       | P2       | 15        | Auth fails after a bad deployment config typo in DB host settings         | 0.63               |
| `ambiguous-incident`   | Medium     | P2       | 25        | Intermittent multi-service failures caused by DNS misconfiguration        | 0.71               |
| `cascading-failure`    | Hard       | P1       | 20        | Runaway analytics query exhausts DB connection pool and cascades failures | 0.458              |
| `memory-leak`          | Hard       | P2       | 25        | Worker OOM crashes from oversized batch processing configuration          | 0.475              |

`POST /reset` also accepts difficulty aliases: `easy` -> `single-service-alert`, `medium` -> `ambiguous-incident`, `hard` -> `cascading-failure`.

Difficulty progression is intentional: isolated service incident (easy) -> ambiguous cross-service investigation with infra evidence gating (medium) -> high-pressure remediation incidents (hard).

## Reward Function

Rewards are per-step and clamped to `[0.01, 0.99]`.

- **Investigation actions**: small positive signal when evidence is relevant.
- **Correct diagnosis**: larger positive signal.
- **Correct remediation or evidence-backed escalation**: highest positive signal.
- **Wrong diagnosis, wrong remediation, or premature escalation**: near-zero credit after penalties.
- **Duplicate actions**: penalized (50% reduction).
- **Step cost**: medium applies a 0.003 per-step cost; hard tasks use stronger pressure (0.006 for cascading-failure, 0.005 for memory-leak).
- **Runbook usage**: agents that consult institutional runbooks (`check_runbook`) receive a small bonus.

Centralized scoring lives in `server/reward.py` and is shared across all scenarios.

## Architecture

```mermaid
flowchart LR
    A[Agent or Baseline Script] --> B[FastAPI Server: server.app]
    B --> C[PraxisEnvironment]
    C --> D[Command Parser]
    C --> E[Scenario Engine]
    E --> F[Single Service Alert]
    E --> G[Cascading Failure]
    E --> H[Ambiguous Incident]
    E --> K[Memory Leak]
    E --> I[Reward Engine]
    I --> C
    C --> J[Observation plus Reward plus Done plus Info]
    J --> A
```

## Baseline Scores

Model: `Qwen/Qwen2.5-72B-Instruct`  
Endpoint: `https://gp5901-praxis.hf.space`

Latest observed live run snapshot (2026-04-10):

| Task                 | Difficulty | Steps | Score |
| -------------------- | ---------- | ----- | ----- |
| single-service-alert | Easy       | 5     | 0.092 |
| cascading-failure    | Hard       | 20    | 0.041 |
| ambiguous-incident   | Medium     | 25    | 0.020 |
| memory-leak          | Hard       | 5     | 0.095 |
| Mean task score      | -          | -     | 0.062 |

Scores can vary between runs based on model behavior and inference endpoint conditions.
Run `python inference.py` to generate a fresh score snapshot.

### Inference Output Contract

`inference.py` emits strict structured lines for judge parsing:

```text
[START] task=<task_name> env=<benchmark> model=<model_name>
[STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
[END] success=<true|false> steps=<n> score=<0.000> rewards=<r1,r2,...,rn>
```

- Per-step rewards are clamped to `[0.01, 0.99]`.
- Task score is computed as mean(step rewards), clamped to `[0.001, 0.999]`.

## Development

Install and test:

```bash
pip install -e ".[dev]"
pytest tests/ -v --tb=short
```

Run contract checks:

```bash
openenv validate
```

Container workflow:

```bash
docker build -t praxis-env:latest .
docker run --rm -p 7860:7860 --name praxis-env praxis-env:latest
```

To add a new scenario, implement a deterministic scenario class under `praxis_env/scenarios/`, register it,
and add task-specific tests under `tests/`.

## API Reference

| Endpoint  | Method | Request                              | Response                                |
| --------- | ------ | ------------------------------------ | --------------------------------------- |
| `/health` | GET    | none                                 | status, version, available tasks        |
| `/tasks`  | GET    | none                                 | task list                               |
| `/reset`  | POST   | none, `{}`, or `{"task_name":"..."}` | initial observation                     |
| `/step`   | POST   | `{"command":"..."}`                  | `observation`, `reward`, `done`, `info` |
| `/state`  | GET    | none                                 | episode metadata                        |

`POST /reset` accepts an optional JSON body. If no body is sent (or `{}` is
sent), the default task is `single-service-alert`.

`observation` in `/step` and `/reset` includes:
`alert_summary`, `system_status`, `investigation_result`, `available_commands`,
`time_elapsed_minutes`, `severity`, `services_affected`, and `step_number`.

The `command` body for `/step` must follow the action templates listed in the
Action Space section.

Minimal request examples:

```bash
curl -X POST http://localhost:7860/reset
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" -d '{}'
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" -d '{"task_name":"single-service-alert"}'
curl -X POST http://localhost:7860/step -H "Content-Type: application/json" -d '{"command":"diagnose root_cause=bad_config"}'
```

## Deployment

Praxis ships with a root Dockerfile and runs on port 7860 for Hugging Face Docker Spaces.
Deployment checklist and commands are in [docs/deployment.md](docs/deployment.md).

## Repository Layout

- `praxis_env/` - package models, client, scenarios
- `server/` - FastAPI app, parser, environment orchestration, reward engine
- `tests/` - scenario, reward, API contract, and inference tests
- `docs/` - detailed technical documentation
- `idea/` - local planning and research notes
