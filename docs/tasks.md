# Tasks

Praxis currently exposes three implemented tasks. Each task is deterministic:
the same command sequence produces the same observations and rewards every run.

Current registered task IDs:

- `single-service-alert`
- `cascading-failure`
- `ambiguous-incident`

Current reward behavior:

- Rewards are signed per step.
- The current implementation clamps per-step rewards to `[-1.0, 1.0]`.
- Final competition-facing score normalization is planned for a later phase.

---

## Task 1: Single Service Alert

**ID**: `single-service-alert`  
**Difficulty**: Easy  
**Severity**: P2  
**Max steps**: 15

### Scenario

The auth service error rate spikes and the API gateway begins degrading as a
downstream symptom. A recent deploy changed the auth database hostname from
`authdb.internal` to `auhdb.internal`, so auth cannot connect to its database.

### What the agent needs to do

1. Investigate auth logs, metrics, config, or dependencies.
2. Diagnose the incident as a bad config or config typo.
3. Roll back the auth deployment.

### Services in scope

| Service    | Initial state | Why                                                   |
| ---------- | ------------- | ----------------------------------------------------- |
| `auth`     | critical      | Cannot reach the database because of the bad hostname |
| `api`      | degraded      | Auth failures cascade upstream                        |
| `payment`  | healthy       | Unaffected service; useful as a contrast              |
| `database` | healthy       | Healthy, but auth cannot reach it                     |

### Scoring (optimal path = 0.60)

| Action                                          | Reward  |
| ----------------------------------------------- | ------- |
| `query_logs service=auth timerange=5m`          | `+0.05` |
| `check_config service=auth`                     | `+0.10` |
| `check_metrics service=auth metric=error_rate`  | `+0.05` |
| `check_metrics service=auth metric=connections` | `+0.05` |
| `check_deps service=auth`                       | `+0.03` |
| `diagnose root_cause=bad_config`                | `+0.20` |
| `rollback_deploy service=auth`                  | `+0.25` |
| Wrong diagnosis                                 | `-0.10` |
| Wrong remediation                               | `-0.05` |
| Escalate after at least 3 investigations        | `+0.15` |

### Notes

- `services_affected` returns service names such as `["auth", "api"]`.
- Observation text is ASCII-normalized even though the source scenario content
  was authored with richer punctuation.

---

## Task 2: Cascading Failure

**ID**: `cascading-failure`  
**Difficulty**: Medium  
**Severity**: P1  
**Max steps**: 20

### Scenario

Three production alerts fire within 90 seconds: API 503s, auth timeouts, and
payment latency. The real problem is a runaway analytics query that consumed
all 100 database connections, leaving no capacity for production traffic.

Current red herrings in the live implementation:

- The API deployment from 14:15 UTC looks suspicious but is healthy.
- Auth memory is elevated to 78%, but that is a symptom of retry pressure.
- Cache hit rate drops, but cache degradation is downstream of the database
  bottleneck.

### What the agent needs to do

1. Recognize the shared dependency pattern across API, auth, and payment.
2. Inspect database connection metrics and database logs.
3. Diagnose the incident as connection-pool exhaustion or runaway query.
4. Resolve by killing the runaway query and scaling the connection pool.

The episode can also end via escalation after at least 3 unique investigations,
but full remediation requires both `kill_query` and `scale_resource`.

### Services in scope

| Service     | Initial state | Why                                                    |
| ----------- | ------------- | ------------------------------------------------------ |
| `api`       | critical      | User-facing failures caused by database timeouts       |
| `auth`      | critical      | Cannot acquire database connections                    |
| `payment`   | degraded      | Falls back to cached read-only behavior                |
| `database`  | degraded      | Pool exhausted by analytics work                       |
| `analytics` | healthy       | Silent root cause; job looks healthy from its own view |
| `cache`     | degraded      | Symptom of retries and stale refresh failures          |

### Scoring (optimal path = 0.75)

| Action                                                     | Reward  |
| ---------------------------------------------------------- | ------- |
| `query_logs service=api timerange=10m`                     | `+0.05` |
| `check_deps service=api`                                   | `+0.05` |
| `check_metrics service=database metric=connections`        | `+0.10` |
| `query_logs service=database timerange=15m`                | `+0.10` |
| `diagnose root_cause=db_connection_pool_exhausted`         | `+0.20` |
| `kill_query service=database query_id=runaway_analytics`   | `+0.15` |
| `scale_resource service=database resource=connection_pool` | `+0.10` |
| Escalate after at least 3 unique investigations            | `+0.15` |
| Wrong diagnosis                                            | `-0.10` |
| Wrong remediation or premature escalation                  | `-0.05` |
| Unknown command                                            | `-0.01` |

### Resolution rules

- Killing the query alone does not finish the episode.
- Scaling the pool alone does not finish the episode.
- The incident resolves only after both remediation steps succeed, or after
  evidence-backed escalation.

### Validation status

Task 2 is implemented and covered by `tests/test_task2_cascading_failure.py`,
including optimal-path, red-herring, determinism, reward-bound, and ASCII-safety checks.

---

## Task 3: Ambiguous Incident

**ID**: `ambiguous-incident`  
**Difficulty**: Hard  
**Severity**: P2  
**Max steps**: 25

### Scenario

Intermittent failures are affecting frontend, api, auth, and search at the
same time. The red herrings are intentional: a healthy api deploy, normal auth
memory variation, and an unrelated long-standing search bug. The real root
cause is an internal DNS misconfiguration introduced during maintenance.

### What the agent needs to do

1. Correlate the failures across several services.
2. Inspect the DNS layer and other infrastructure signals.
3. Diagnose the incident as a DNS misconfiguration or DNS failure.
4. Resolve the issue by restarting `dns-resolver` or escalating with evidence.

### Services in scope

| Service         | Initial state | Why                                                      |
| --------------- | ------------- | -------------------------------------------------------- |
| `frontend`      | degraded      | Intermittent NXDOMAIN and timeout errors                 |
| `api`           | degraded      | Upstream lookup failures and retries                     |
| `auth`          | degraded      | Retry pressure and intermittent timeouts                 |
| `search`        | degraded      | Slowdowns plus unrelated bug noise                       |
| `dns-resolver`  | degraded      | The actual root cause                                    |
| `load-balancer` | healthy       | Infrastructure dependency that helps confirm the pattern |
| `cache`         | healthy       | Symptom of retries, not the cause                        |

### Scoring

| Action                                                          | Reward  |
| --------------------------------------------------------------- | ------- |
| `query_logs service=frontend timerange=10m`                     | `+0.05` |
| `query_logs service=api timerange=10m`                          | `+0.05` |
| `query_logs service=auth timerange=10m`                         | `+0.05` |
| `check_deps service=frontend`                                   | `+0.03` |
| `check_metrics service=dns-resolver metric=resolution_failures` | `+0.10` |
| `query_logs service=dns-resolver timerange=30m`                 | `+0.10` |
| `check_config service=dns-resolver`                             | `+0.05` |
| `diagnose root_cause=dns_misconfiguration`                      | `+0.20` |
| `restart_service service=dns-resolver`                          | `+0.15` |
| `escalate` after evidence                                       | `+0.15` |
| Premature diagnosis                                             | `-0.10` |
| Premature escalation                                            | `-0.05` |

### Evidence Rules

- Diagnosis only becomes valid after at least 3 unique services are investigated.
- At least one infrastructure signal must be checked before diagnosis.
- Escalation is only rewarded after the same evidence threshold is met.
- Blind remediation of `dns-resolver` is penalized.

### Validation status

Task 3 is now implemented and covered by `tests/test_task3_ambiguous_incident.py`,
including optimal-path, evidence-threshold, red-herring, determinism, and
reward-bound checks.

---

## Querying available tasks

```bash
curl http://localhost:7860/tasks
```

Current response:

```json
{
  "tasks": ["ambiguous-incident", "cascading-failure", "single-service-alert"]
}
```
