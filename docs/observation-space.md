# Observation Space

Every response from `POST /reset` and `POST /step` includes a
`PraxisObservation` payload.

Current behavior to document:

- `alert_summary` and `investigation_result` are ASCII-normalized.
- `services_affected` contains service names, not status labels.
- `time_elapsed_minutes` advances by `2.5` minutes per completed step.

---

## Fields

| Field | Type | Description |
|---|---|---|
| `alert_summary` | `string` | Current incident description in ASCII-safe markdown text |
| `system_status` | `object` | Map of service name to status |
| `investigation_result` | `string` | Output of the most recent command; empty on reset |
| `available_commands` | `array[string]` | Command templates supported by the server |
| `time_elapsed_minutes` | `float` | Elapsed incident time based on completed steps |
| `severity` | `string` | One of `P0`, `P1`, `P2`, `P3` |
| `services_affected` | `array[string]` | Service names whose current status is not `healthy` |
| `step_number` | `integer` | Current completed-step count |

---

## `system_status`

Each service maps to one of four health states:

| Status | Meaning |
|---|---|
| `healthy` | Service is operating normally |
| `degraded` | Service is partially impacted |
| `critical` | Service is heavily impacted |
| `down` | Service is unavailable |

Example:

```json
{
  "auth": "critical",
  "api": "degraded",
  "payment": "healthy",
  "database": "healthy"
}
```

---

## `severity`

| Level | Meaning |
|---|---|
| `P0` | Complete outage |
| `P1` | Major degradation |
| `P2` | Partial degradation |
| `P3` | Minor issue |

---

## Text normalization

The live code normalizes scenario text to ASCII before it leaves the server.
This keeps Windows console output, test snapshots, and local debugging stable.

Examples of what that means in practice:

- rich punctuation is flattened to ASCII equivalents
- emoji-style alert markers are removed or replaced
- payload examples in these docs should stay ASCII-safe too

---

## `investigation_result`

This field depends on the command just executed.

After `query_logs`:

```text
14:27:01 [ERROR] Connection refused: postgres://auhdb.internal:5432/authdb
14:27:15 [ERROR] Token validation failed - database unreachable
14:27:30 [WARN]  Retrying database connection (attempt 3/3)... failed
```

After `check_metrics`:

```text
error_rate
  Current (1m):  15.2%
  1h average:     8.1%
  24h average:    0.12%
```

After `check_deps`:

```text
auth service dependencies:
  -> database  [postgres://auhdb.internal:5432/authdb]  FAILING - host unreachable
```

After an invalid command:

```text
Unknown command: 'foo bar'

Available commands:
  query_logs service=<name> timerange=<N>m
  check_metrics service=<name> metric=<type>
  ...
```

---

## Full example response

```json
{
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
  "time_elapsed_minutes": 7.5,
  "severity": "P2",
  "services_affected": ["auth", "api"],
  "step_number": 3
}
```
