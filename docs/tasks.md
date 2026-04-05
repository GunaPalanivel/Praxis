# Tasks

Praxis has three tasks that escalate in difficulty. Each is a self-contained incident with deterministic state — the same commands always produce the same results.

---

## Task 1: Single Service Alert

**ID**: `single-service-alert`  
**Difficulty**: Easy  
**Severity**: P2  
**Max steps**: 15

### Scenario

The auth service error rate has spiked to **15.2%** (normal: 0.1%). Users are unable to log in or refresh their sessions. The API gateway is also showing elevated errors as a downstream symptom.

**Root cause**: A deployment at 14:23 UTC introduced a typo in the database hostname — `auhdb.internal` instead of `authdb.internal`. The auth service can't connect to its database.

### What the agent needs to do

1. **Investigate** — query auth logs or check config to find the hostname typo
2. **Diagnose** — identify the root cause (`bad_config` or `config_typo`)
3. **Remediate** — roll back the bad deployment (`rollback_deploy service=auth`)

### Services in scope

| Service | Initial state | Why |
|---|---|---|
| `auth` | critical | Can't connect to database |
| `api` | degraded | Auth failures cascade upstream |
| `payment` | healthy | Red herring — unrelated |
| `database` | healthy | Healthy, but not being reached |

### Scoring (optimal path ≈ 0.60)

| Action | Reward |
|---|---|
| Query auth logs | +0.05 |
| Check auth config | +0.10 _(reveals typo directly)_ |
| Check metrics (error_rate or connections) | +0.05 each |
| Check deps | +0.03 |
| Correct diagnosis | +0.20 |
| Correct remediation (rollback auth) | +0.25 |
| Wrong diagnosis | −0.10 |
| Wrong remediation target | −0.05 |
| Escalate with ≥3 investigations | +0.15 _(alternative ending)_ |

### Red herrings

- API gateway is degraded — it's a **symptom** not the cause
- Auth service has high latency — **caused by** connection timeouts, not a capacity issue
- Restarting auth service will fail — the config typo persists after restart

---

## Task 2: Cascading Failure

**ID**: `cascading-failure`  
**Difficulty**: Medium  
**Severity**: P1  
**Max steps**: 20

> ⚠️ Coming in Phase 4. The endpoint is registered but not yet implemented.

### Preview

A database connection pool exhaustion event triggers a cascade across 3 services. The agent must distinguish the root service from the downstream symptoms and apply the right fix without worsening the situation.

---

## Task 3: Ambiguous Incident

**ID**: `ambiguous-incident`  
**Difficulty**: Hard  
**Severity**: P1  
**Max steps**: 25

> ⚠️ Coming in Phase 5. The endpoint is registered but not yet implemented.

### Preview

A DNS misconfiguration is causing intermittent failures across 4+ services with no single obvious smoking gun. Evidence is spread across logs, metrics, and the dependency graph. Multiple plausible diagnoses exist — the agent must correlate across data sources to find the real root cause.

---

## Querying available tasks

```bash
curl http://localhost:7860/tasks
# → {"tasks": ["single-service-alert"]}  (more added in Phases 4 and 5)
```
