# Observation Space

Every response from `POST /reset` and `POST /step` includes an observation object with these fields.

## Fields

| Field | Type | Description |
|---|---|---|
| `alert_summary` | `string` | Markdown-formatted incident description. Always present. |
| `system_status` | `object` | Map of service name → health status |
| `investigation_result` | `string` | Output of the last command. Empty string on first observation. |
| `available_commands` | `array[string]` | Command templates the agent can use |
| `time_elapsed_minutes` | `float` | Minutes since the incident started (increases each step) |
| `severity` | `string` | Incident severity: `"P0"` · `"P1"` · `"P2"` · `"P3"` |
| `services_affected` | `array[string]` | Services currently showing issues |
| `step_number` | `integer` | Current step count (0 on reset, increments with each step) |

---

## `system_status`

Each service maps to one of four health states:

| Status | Meaning |
|---|---|
| `"healthy"` | Service is operating normally |
| `"degraded"` | Service is experiencing elevated errors or latency |
| `"critical"` | Service is largely failing; major user impact |
| `"down"` | Service is completely unavailable |

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
| `P0` | Complete outage — all users affected |
| `P1` | Major degradation — most users affected |
| `P2` | Partial degradation — some users affected |
| `P3` | Minor issue — few users affected |

---

## `investigation_result`

The text output of the last command. Content depends on the command issued:

**After `query_logs`:**
```
14:27:01 [ERROR] Connection refused: postgres://db.internal:5432/auhdb
14:28:15 [ERROR] Connection refused: postgres://db.internal:5432/auhdb
14:29:00 [ERROR] Connection pool exhausted
14:30:22 [WARN] Health check failed
```

**After `check_metrics`:**
```
error_rate → Current: 15.2% | 1h avg: 8.1% | 24h avg: 0.12%
```

**After `check_deps`:**
```
auth depends on: [database]
  database → healthy
Connection string: postgres://db.internal:5432/auhdb
```

**After an invalid command:**
```
Unknown command: 'foo bar'. Available commands:
  query_logs service=<name> timerange=<N>m
  check_metrics service=<name> metric=<type>
  ...
```

---

## Full Example Response

```json
{
  "alert_summary": "## 🚨 INCIDENT ALERT\n\n**Alert ID**: AUTH-001\n...",
  "system_status": {
    "auth": "critical",
    "api": "healthy",
    "payment": "healthy",
    "database": "healthy"
  },
  "investigation_result": "14:27:01 [ERROR] Connection refused: postgres://db.internal:5432/auhdb\n...",
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
  "services_affected": ["auth"],
  "step_number": 3
}
```
