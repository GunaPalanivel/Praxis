# API Reference

HTTP API specification for the Praxis environment server.

**Base URL (local):** `http://localhost:7860`  
**Base URL (HF Spaces):** `https://your-space.hf.space`

All request and response bodies are JSON. All endpoints return `Content-Type: application/json`.

---

## `POST /reset`

Start a new episode. Resets all episode state cleanly.

### Request

```json
{
  "task_name": "single-service-alert"
}
```

| Field | Type | Default | Values |
|---|---|---|---|
| `task_name` | string | `"single-service-alert"` | `"single-service-alert"` · `"cascading-failure"` · `"ambiguous-incident"` |

### Response `200 OK`

Returns the initial [PraxisObservation](./observation-space.md):

```json
{
  "alert_summary": "## 🚨 INCIDENT ALERT\n\n**Alert ID**: AUTH-001\n...",
  "system_status": { "auth": "critical", "api": "healthy", "database": "healthy" },
  "investigation_result": "",
  "available_commands": ["query_logs service=<name> timerange=<N>m", "..."],
  "time_elapsed_minutes": 0.0,
  "severity": "P2",
  "services_affected": ["auth"],
  "step_number": 0
}
```

### Error Responses

| Status | When |
|---|---|
| `400` | Unknown `task_name` |
| `500` | Internal server error |

---

## `POST /step`

Execute one action in the current episode.

**Must call `/reset` first.** Returns 400 if called before reset.

### Request

```json
{
  "command": "query_logs service=auth timerange=5m"
}
```

| Field | Type | Description |
|---|---|---|
| `command` | string | Any [action command](./action-space.md) |

### Response `200 OK`

```json
{
  "observation": {
    "alert_summary": "...",
    "system_status": { "auth": "critical" },
    "investigation_result": "14:27:01 [ERROR] Connection refused...",
    "available_commands": ["..."],
    "time_elapsed_minutes": 2.5,
    "severity": "P2",
    "services_affected": ["auth"],
    "step_number": 1
  },
  "reward": 0.05,
  "done": false,
  "info": {}
}
```

| Field | Type | Description |
|---|---|---|
| `observation` | object | New [PraxisObservation](./observation-space.md) |
| `reward` | float | Per-step reward in `[0.0, 1.0]` |
| `done` | boolean | `true` when episode has ended |
| `info` | object | Optional debug info (empty in normal flow) |

### Error Responses

| Status | When |
|---|---|
| `400` | Called before `/reset` |
| `500` | Internal error |

---

## `GET /state`

Get current episode metadata without the full observation.

**Must call `/reset` first.**

### Response `200 OK`

```json
{
  "episode_id": "single-service-alert_1",
  "step_count": 3,
  "task_name": "single-service-alert",
  "incident_resolved": false,
  "root_cause_identified": true,
  "cumulative_reward": 0.30
}
```

| Field | Type | Description |
|---|---|---|
| `episode_id` | string | Unique ID for this episode |
| `step_count` | int | Steps taken so far |
| `task_name` | string | Active scenario |
| `incident_resolved` | boolean | Incident fully resolved |
| `root_cause_identified` | boolean | Correct diagnosis issued |
| `cumulative_reward` | float | Sum of rewards so far |

---

## `GET /tasks`

List all registered task names.

### Response `200 OK`

```json
{
  "tasks": [
    "single-service-alert",
    "cascading-failure",
    "ambiguous-incident"
  ]
}
```

---

## `GET /health`

Health check endpoint. Used by the pre-submission validator.

### Response `200 OK`

```json
{
  "status": "ok",
  "environment": "praxis-env",
  "version": "1.0.0",
  "available_tasks": ["single-service-alert", "cascading-failure", "ambiguous-incident"]
}
```

---

## Episode Flow

```
POST /reset {"task_name": "..."} → initial observation
   ↓
POST /step  {"command": "query_logs ..."} → observation, reward=0.05, done=false
POST /step  {"command": "check_metrics ..."} → observation, reward=0.05, done=false
POST /step  {"command": "diagnose ..."} → observation, reward=0.20, done=false
POST /step  {"command": "rollback_deploy ..."} → observation, reward=0.25, done=true
   ↓
POST /reset → new clean episode (or use a different task_name)
```

## Client Example

```python
import httpx

async def run_episode(base_url: str, task: str, commands: list[str]):
    async with httpx.AsyncClient(base_url=base_url) as client:
        obs = (await client.post("/reset", json={"task_name": task})).json()
        rewards = []

        for cmd in commands:
            resp = (await client.post("/step", json={"command": cmd})).json()
            rewards.append(resp["reward"])
            if resp["done"]:
                break

        return sum(rewards)
```
