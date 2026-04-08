# API Reference

HTTP API specification for the current Praxis environment server.

**Base URL (local):** `http://localhost:7860`

All request and response bodies are JSON.

Current routes:

- `POST /reset`
- `POST /step`
- `GET /state`
- `GET /tasks`
- `GET /health`

Notes about the current contract:

- `alert_summary` and `investigation_result` are ASCII-normalized text payloads.
- `services_affected` is an array of service names with non-healthy status.
- Per-step `reward` is centrally computed and bounded to `[0.0, 1.0]`.

---

## `POST /reset`

Start a new episode and clear all previous episode state.

### Request

The request body is optional. All three forms below are valid:

- No body (defaults to `single-service-alert`)
- Empty JSON object (`{}`)
- Explicit task selection (`{"task_name": "..."}`)

```json
{
  "task_name": "single-service-alert"
}
```

| Field       | Type   | Default                  | Current values                                                             |
| ----------- | ------ | ------------------------ | -------------------------------------------------------------------------- |
| `task_name` | string | `"single-service-alert"` | `"single-service-alert"`, `"cascading-failure"`, or `"ambiguous-incident"` |

### Response `200 OK`

```json
{
  "alert_summary": "## INCIDENT ALERT\n\n**Alert ID**: AUTH-001\n...",
  "system_status": {
    "auth": "critical",
    "api": "degraded",
    "payment": "healthy",
    "database": "healthy"
  },
  "investigation_result": "",
  "available_commands": [
    "query_logs service=<name> timerange=<N>m",
    "check_metrics service=<name> metric=<type>",
    "check_deps service=<name>",
    "check_config service=<name>",
    "diagnose root_cause=<cause>",
    "restart_service service=<name>",
    "rollback_deploy service=<name>",
    "scale_resource service=<name> resource=<type>",
    "kill_query service=<name> query_id=<id>",
    "escalate reason=<text>"
  ],
  "time_elapsed_minutes": 0.0,
  "severity": "P2",
  "services_affected": ["auth", "api"],
  "step_number": 0
}
```

### Error responses

| Status | When                  |
| ------ | --------------------- |
| `400`  | Unknown `task_name`   |
| `500`  | Internal server error |

---

## `POST /step`

Execute one action in the current episode.

You must call `/reset` first.

### Request

```json
{
  "command": "query_logs service=auth timerange=5m"
}
```

| Field     | Type   | Description                                                                        |
| --------- | ------ | ---------------------------------------------------------------------------------- |
| `command` | string | Any valid or invalid command string; invalid input returns a handled error payload |

### Response `200 OK`

```json
{
  "observation": {
    "alert_summary": "## INCIDENT ALERT\n\n**Alert ID**: AUTH-001\n...",
    "system_status": {
      "auth": "critical",
      "api": "degraded",
      "payment": "healthy",
      "database": "healthy"
    },
    "investigation_result": "14:27:01 [ERROR] Connection refused: postgres://auhdb.internal:5432/authdb\n...",
    "available_commands": [
      "query_logs service=<name> timerange=<N>m",
      "check_metrics service=<name> metric=<type>",
      "check_deps service=<name>",
      "check_config service=<name>",
      "diagnose root_cause=<cause>",
      "restart_service service=<name>",
      "rollback_deploy service=<name>",
      "scale_resource service=<name> resource=<type>",
      "kill_query service=<name> query_id=<id>",
      "escalate reason=<text>"
    ],
    "time_elapsed_minutes": 2.5,
    "severity": "P2",
    "services_affected": ["auth", "api"],
    "step_number": 1
  },
  "reward": 0.05,
  "done": false,
  "info": {}
}
```

| Field         | Type    | Description                           |
| ------------- | ------- | ------------------------------------- |
| `observation` | object  | The new observation after the command |
| `reward`      | float   | Per-step reward in `[0.0, 1.0]`       |
| `done`        | boolean | `true` when the episode has ended     |
| `info`        | object  | Optional debug metadata               |

### Error responses

| Status | When                   |
| ------ | ---------------------- |
| `400`  | Called before `/reset` |
| `500`  | Internal error         |

---

## `GET /state`

Get current episode metadata without the full observation.

### Response `200 OK`

```json
{
  "episode_id": "single-service-alert_1",
  "step_count": 3,
  "task_name": "single-service-alert",
  "incident_resolved": false,
  "root_cause_identified": true,
  "cumulative_reward": 0.3
}
```

| Field                   | Type    | Description                                                       |
| ----------------------- | ------- | ----------------------------------------------------------------- |
| `episode_id`            | string  | Unique ID for the current episode                                 |
| `step_count`            | integer | Number of completed steps                                         |
| `task_name`             | string  | Active scenario ID                                                |
| `incident_resolved`     | boolean | Whether the incident has been resolved or escalated to completion |
| `root_cause_identified` | boolean | Whether a correct diagnosis has been issued                       |
| `cumulative_reward`     | float   | Sum of per-step rewards so far                                    |

---

## `GET /tasks`

List all currently registered task IDs.

### Response `200 OK`

```json
{
  "tasks": ["ambiguous-incident", "cascading-failure", "single-service-alert"]
}
```

---

## `GET /health`

Basic health check used for local verification.

### Response `200 OK`

```json
{
  "status": "ok",
  "environment": "praxis-env",
  "version": "1.0.0",
  "available_tasks": [
    "ambiguous-incident",
    "cascading-failure",
    "single-service-alert"
  ]
}
```

---

## Episode flow

```text
POST /reset {"task_name": "single-service-alert"}
  -> observation step_number=0

POST /step {"command": "query_logs service=auth timerange=5m"}
  -> observation, reward=0.05, done=false

POST /step {"command": "diagnose root_cause=bad_config"}
  -> observation, reward=0.20, done=false

POST /step {"command": "rollback_deploy service=auth"}
  -> observation, reward=0.25, done=true
```

The current HTTP surface is limited to the endpoints documented above.

The live `/reset` endpoint currently accepts these task names:

- `single-service-alert`
- `cascading-failure`
- `ambiguous-incident`
