# Action Space

Every action the agent sends is a single command string parsed by the environment.

## Command Grammar

```
<action_type> [key=value ...]
```

All commands use this format. The environment parses `key=value` pairs separated by spaces. The `escalate` command is a special case — everything after `reason=` is treated as free text.

---

## Investigation Commands

These commands gather information. They never change system state.

### `query_logs`

Query recent log lines from a service.

```
query_logs service=<name> timerange=<N>m
```

| Parameter   | Required | Values                           | Example                   |
| ----------- | -------- | -------------------------------- | ------------------------- |
| `service`   | Yes      | Any service name                 | `auth`, `api`, `database` |
| `timerange` | No       | Minutes, e.g. `5m`, `15m`, `30m` | `5m`                      |

**Example:**

```
query_logs service=auth timerange=5m
query_logs service=database timerange=15m
```

**Returns:** Recent log lines from that service in the specified window.

**Reward:** `+0.03` to `+0.05` per unique relevant investigation.

---

### `check_metrics`

Check a specific metric for a service.

```
check_metrics service=<name> metric=<type>
```

| Parameter | Required | Values                 |
| --------- | -------- | ---------------------- |
| `service` | Yes      | Any service name       |
| `metric`  | Yes      | See metric types below |

**Metric types:**

| Metric                | What it shows                           |
| --------------------- | --------------------------------------- |
| `error_rate`          | Percentage of requests returning errors |
| `latency_p95`         | 95th percentile latency in milliseconds |
| `throughput`          | Requests per second                     |
| `connections`         | Active connections (e.g. DB pool)       |
| `memory`              | Memory utilization (0.0–1.0)            |
| `cpu`                 | CPU utilization (0.0–1.0)               |
| `resolution_failures` | DNS resolution failure rate             |
| `cache_hit_rate`      | Cache hit percentage                    |

**Example:**

```
check_metrics service=database metric=connections
check_metrics service=auth metric=error_rate
```

**Returns:** Current value, 1h average, and 24h average.

**Reward:** `+0.03` to `+0.10` for metrics that reveal root-cause-relevant data.

---

### `check_deps`

View the dependency graph for a service — what it depends on.

```
check_deps service=<name>
```

**Example:**

```
check_deps service=api
```

**Returns:** List of services this service depends on, with their current health status.

**Reward:** `+0.03` for unique dependency checks.

---

### `check_config`

View recent configuration changes for a service.

```
check_config service=<name>
```

**Example:**

```
check_config service=auth
```

**Returns:** Timestamped list of recent config changes with diffs.

**Reward:** `+0.05` — especially valuable when a deploy/config is the root cause.

---

### `check_runbook`

Check the institutional runbook for standard triage steps for a service.

```
check_runbook service=<name>
```

**Example:**

```
check_runbook service=frontend
```

**Returns:** The structured standard operating procedures for the service.

**Reward:** `+0.05` (runbook bonus) — encourages agents to follow structured institutional knowledge.

---

## Diagnosis Command

### `diagnose`

Declare the root cause of the incident. Can be submitted once.

```
diagnose root_cause=<cause>
```

**Common root cause values:**

| Value                          | When to use                                          |
| ------------------------------ | ---------------------------------------------------- |
| `bad_config`                   | A config change introduced a typo or incorrect value |
| `config_typo`                  | Same as above                                        |
| `db_connection_pool_exhausted` | Database connection pool saturated                   |
| `runaway_query`                | A database query consuming all resources             |
| `dns_misconfiguration`         | DNS resolver configured incorrectly                  |
| `deployment_failure`           | A deployment introduced a breaking change            |

**Reward:**

- Correct: `+0.20`
- Incorrect: `0.00` (no credit)

> **Tip:** Gather evidence from multiple services before diagnosing. Premature diagnosis without investigation usually leads to wrong guesses.

---

## Remediation Commands

These commands change system state. Use only after diagnosis.

### `restart_service`

Restart a service. Use when a service is stuck or unresponsive.

```
restart_service service=<name>
```

**Reward:** `+0.15` if correct target, `0.00` if wrong target.

> ⚠️ Don't restart symptom services — find the root cause first.

---

### `rollback_deploy`

Roll back the latest deployment for a service.

```
rollback_deploy service=<name>
```

**Reward:** `+0.25` if the deployment was the root cause, `0.00` if not.

---

### `scale_resource`

Scale a resource for a service (e.g. increase DB connection pool).

```
scale_resource service=<name> resource=<type>
```

| `resource` values |
| ----------------- |
| `connection_pool` |
| `replicas`        |
| `memory_limit`    |

**Reward:** `+0.10` if appropriate for the situation.

---

### `kill_query`

Kill a specific database query consuming resources.

```
kill_query service=<name> query_id=<id>
```

The `query_id` is revealed in the database log output when you run `query_logs service=database`.

**Reward:** `+0.15` if the query is the root cause.

---

## Escalation Command

### `escalate`

Hand off the incident to a human with a documented reason. A valid strategy when the situation is genuinely complex.

```
escalate reason=<free text explanation>
```

**Example:**

```
escalate reason=DNS misconfiguration affecting all internal services since 16:30 maintenance window. Evidence: elevated resolution_failures on dns-resolver, correlated errors across frontend/api/auth
```

**Reward:**

- With sufficient evidence (≥3 investigations): `+0.15`
- Without evidence: `0.00`

> Escalation is **not** giving up — it's a valid incident response action when you have evidence but lack the access to fix the root cause directly. Include your evidence in the `reason`.

---

## Invalid Commands

Any unrecognized command returns an error response but does **not** crash the environment:

```
unknown_command foo=bar
# → "Unknown command: 'unknown_command foo=bar'
#    Available commands: ..."
# Reward: 0.00
```

The episode continues after an invalid command.
