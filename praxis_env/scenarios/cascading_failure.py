"""
praxis_env.scenarios.cascading_failure — Task 2: Cascading Failure.

Difficulty: Medium
Severity: P1
Max Steps: 20

Incident Summary:
  Multiple services alerting simultaneously — API is returning 503s,
  Auth is timing out, Payment service is slow. Three alerts fired at once,
  which is the first sign this is a cascading failure, not isolated.

Root cause: A runaway analytics pipeline launched a full-table scan
  against the production database at 14:45 UTC. This exhausted the
  database connection pool (100/100 connections used), leaving nothing
  for API, Auth, and Payment to connect. All three degrade simultaneously.

Red herrings (by design — EGAR test):
  1. API deployment happened 30 minutes ago at 14:15 UTC — deployment
    is healthy and has nothing to do with the incident. An agent that
    blames this receives no diagnosis credit.
  2. Auth service memory at 78% — normal variation under load, not a
     contributing cause. Auth degradation is a symptom of DB pool exhaustion.
  3. Cache hit rate dropped — symptom of increased load as services retry,
     not an independent cause.

Optimal path (7 steps, score ≈ 0.75):
  1. query_logs service=api timerange=10m          → 503s citing DB timeout     (+0.05)
  2. check_deps service=api                        → api→database dependency    (+0.05)
  3. check_metrics service=database metric=connections → pool 100/100!          (+0.10)
  4. query_logs service=database timerange=15m     → slow query from analytics  (+0.10)
  5. diagnose root_cause=db_connection_pool_exhausted → CORRECT                (+0.20)
  6. kill_query service=database query_id=runaway_analytics                     (+0.15)
  7. scale_resource service=database resource=connection_pool                   (+0.10)

Alternative valid ending (steps 5→6 skipped):
  escalate with ≥3 investigations → +0.15

Red herring penalties:
    - diagnose root_cause=api_deployment → 0.00 (no credit)
    - diagnose root_cause=memory_pressure → 0.00 (no credit)
    - restart_service service=auth → 0.00 (symptom treatment)
    - rollback_deploy service=api → 0.00 (wrong remediation)

EGAR score target:
  - Naive agent that blames API deploy: ~0.10-0.15
  - Correct agent (full optimal path):  ~0.75
  This spread > 0.50 shows strong discriminative power.
"""

from __future__ import annotations

from praxis_env.scenarios.base import (
    BaseScenario,
    ParsedCommand,
    StepOutcome,
    get_metric_param,
    get_service_param,
)


class CascadingFailureScenario(BaseScenario):
    """Task 2: Multiple services fail due to a runaway analytics query exhausting the DB pool."""

    NAME = "cascading-failure"
    SEVERITY = "P1"
    MAX_STEPS = 20

    ALERT_SUMMARY = """\
## 🚨 MULTI-SERVICE INCIDENT

**Alert ID**: MULTI-001
**Severity**: P1 — Major degradation (significant user impact)
**Triggered**: 14:47 UTC (3 alerts fired within 90 seconds)
**Duration**: ~5 minutes and worsening

**Active Alerts**:
- ❌ api-gateway:     HTTP 503 error rate 34% (threshold: 10%)
- ❌ auth:            Response timeout rate 28% (threshold: 5%)
- ⚠️ payment-service: Latency P95 = 8.4s (threshold: 2s)

**System status**:
- api:       ❌ critical
- auth:      ❌ critical
- payment:   ⚠️  degraded
- database:  ⚠️  degraded
- analytics: ✅ healthy (self-reported)
- cache:     ⚠️  degraded

**Context**:
- All 3 services began degrading within 90 seconds of each other
- API deployment v3.2.1 was released 30 minutes ago at 14:15 UTC
- This pattern (multi-service simultaneous degradation) suggests a shared dependency

Investigate the root cause. Multiple services are affected — follow the dependency graph.\
"""

    INITIAL_SYSTEM_STATUS = {
        "api": "critical",
        "auth": "critical",
        "payment": "degraded",
        "database": "degraded",
        "analytics": "healthy",
        "cache": "degraded",
    }

    INITIAL_AFFECTED_SERVICES = ["api", "auth", "payment", "database", "cache"]

    # ── Pre-computed investigation data ───────────────────────────────────────

    _LOGS = {
        "api": """\
14:47:02 [ERROR] Upstream timeout: database connection refused
14:47:03 [ERROR] Upstream timeout: database connection refused
14:47:05 [ERROR] POST /api/login → 503 (upstream auth timeout)
14:47:07 [ERROR] POST /api/payments → 503 (upstream payment timeout)
14:47:10 [ERROR] DB connection pool timeout after 5000ms
14:47:12 [WARN]  Circuit breaker opening for database upstream
14:47:15 [ERROR] DB connection pool timeout after 5000ms
14:47:30 [ERROR] 503 rate: 34.2% (all routes affected)
14:47:45 [WARN]  Health check: database → UNHEALTHY (pool exhausted)
14:48:00 [ERROR] Reject request: no DB connections available (pool: 100/100 in use)

Note: All errors trace back to database connection pool exhaustion.
Last healthy checkpoint: 14:45:30 UTC
""",
        "auth": """\
14:46:55 [WARN]  Database query timeout: SELECT * FROM sessions WHERE... (took 12s)
14:47:00 [ERROR] Auth: Cannot acquire database connection (pool full)
14:47:05 [ERROR] Token validation failed: database unreachable
14:47:10 [ERROR] Session lookup failed: database unreachable
14:47:15 [WARN]  Memory: 78% (within normal operating range under load)
14:47:20 [ERROR] Login attempt rejected: database unavailable
14:47:30 [WARN]  Auth response time P95: 9200ms (SLO: 500ms)
14:47:45 [ERROR] Cannot acquire database connection — pool exhausted

Note: Auth failures are ALL caused by database unavailability.
Auth memory at 78% is normal — not contributing to the incident.
""",
        "payment": """\
14:46:58 [WARN]  Database connection slow: took 4200ms to acquire
14:47:05 [WARN]  Payment gateway latency elevated: 8400ms
14:47:10 [ERROR] Payment: database connection pool timeout
14:47:20 [WARN]  Retrying failed DB connection (1/3)
14:47:30 [WARN]  Retrying failed DB connection (2/3)
14:47:40 [ERROR] Payment: database all retries exhausted — degraded mode
14:48:00 [WARN]  Payment operating in degraded mode (read-only cached data)

Note: Payment is degraded but not down — it has a read-only cache fallback.
Database connection is the bottleneck.
""",
        "database": """\
14:44:30 [INFO]  New long-running query started: analytics_pipeline (PID 8847)
14:44:35 [WARN]  Query analytics_pipeline: full table scan on events table (3.2B rows)
14:45:00 [WARN]  analytics_pipeline: acquired 45 connections (pool: 45/100 used)
14:45:30 [WARN]  analytics_pipeline: acquired 72 connections (pool: 72/100 used)
14:46:00 [WARN]  analytics_pipeline: acquired 91 connections (pool: 91/100 used)
14:46:30 [ERROR] analytics_pipeline: acquired 100 connections (pool: 100/100 — FULL)
14:46:45 [ERROR] Connection refused: pool exhausted — new requests failing
14:47:00 [ERROR] api, auth, payment: connection timeout (pool full)
14:47:30 [ERROR] 38 queries queued waiting for connections

RUNAWAY QUERY DETAILS:
PID: 8847 | User: analytics | Status: RUNNING
Query: SELECT * FROM events WHERE date >= '2020-01-01' (no index, full scan)
Duration: 3m 15s | Connections held: 100

Note: This query has no LIMIT clause and no index on date column.
""",
        "analytics": """\
14:44:25 [INFO]  Analytics pipeline job started: weekly_event_aggregation
14:44:30 [INFO]  Connecting to production database
14:45:00 [INFO]  Running: SELECT * FROM events WHERE date >= '2020-01-01'
14:45:30 [WARN]  Query running long (60s) — no timeout configured
14:46:00 [WARN]  Query still running (90s)
14:46:30 [WARN]  Query still running (120s) — pool connections held

Note: Analytics pipeline does NOT see itself as unhealthy.
It believes it is performing normal work.
This is a misconfigured pipeline with no connection limits and no query timeout.
""",
        "cache": """\
14:46:45 [WARN]  Cache hit rate dropping: 94% → 71%
14:47:00 [WARN]  Cache miss spike: services retrying DB calls, bypassing cache
14:47:30 [WARN]  Cache hit rate: 58% (normal: 95%)
14:48:00 [INFO]  Cache memory: 42% utilisation (healthy)

Note: Cache degradation is a SYMPTOM — services are bypassing the cache
because database connections aren't available to refresh stale data.
Cache itself is functionally healthy.
""",
    }

    _METRICS = {
        ("api", "error_rate"): """\
error_rate (api-gateway)
  Current (1m):  34.2%
  1h avg:         2.1%
  24h avg:        0.18%
  Threshold:     10.0%  🔴 BREACH
  Pattern: Error rate began rising at exactly 14:46:45 UTC.
""",
        ("api", "latency_p95"): """\
latency_p95 (api-gateway)
  Current:  9800ms  ← dominated by DB connection timeouts (5s limit)
  1h avg:    180ms
  24h avg:   172ms
""",
        ("auth", "error_rate"): """\
error_rate (auth)
  Current:  28.4%
  1h avg:    0.9%
  24h avg:   0.12%
  Pattern: Errors began at 14:46:50 UTC — 5 seconds after API errors started.
""",
        ("auth", "memory"): """\
memory (auth)
  Current:  78%
  1h avg:   72%
  24h avg:  68%
  Threshold: 90%  ✅ NOT IN BREACH
  Note: 78% is normal under elevated load. Not a contributing factor.
""",
        ("auth", "connections"): """\
connections (auth → database)
  Active DB connections:  0 (all requests failing to acquire)
  Failed connection attempts (last 5m): 847
  Pool wait timeout: 5000ms
""",
        ("payment", "latency_p95"): """\
latency_p95 (payment)
  Current:  8400ms
  1h avg:    310ms
  24h avg:   290ms
  SLO:       2000ms  🔴 BREACH
""",
        ("database", "connections"): """\
connections (database)
  POOL STATUS: 100/100 (FULL — EXHAUSTED) 🔴
  Used by analytics_pipeline: 100
  Used by api:                  0  ← waiting
  Used by auth:                 0  ← waiting
  Used by payment:              0  ← waiting
  Max pool size: 100
  Queued requests: 38

This is the root cause: analytics_pipeline has consumed the entire connection pool.
""",
        ("database", "error_rate"): """\
error_rate (database)
  Connection refused rate: 38 req/min (all from api, auth, payment)
  Query error rate: 0.0% (no query errors — queries just can't get connections)
""",
        ("database", "cpu"): """\
cpu (database)
  Current: 89%  ← running the analytics full-table scan
  1h avg:  24%
  24h avg: 18%
  Note: High CPU is caused by the huge unindexed scan.
""",
        ("analytics", "throughput"): """\
throughput (analytics)
  Current: 1 active job (weekly_event_aggregation)
  Status: RUNNING — started 14:44:30 UTC
  Duration: 3m 45s (and still running)
  Note: No SLA or timeout configured on this job.
""",
        ("cache", "cache_hit_rate"): """\
cache_hit_rate
  Current:  58%  (normal: 95%)  ← dropped as services retry DB
  1h avg:   91%
  24h avg:  94%
  Cache is operationally healthy — this is a symptom of DB pool exhaustion.
""",
    }

    _DEPS = {
        "api": """\
api-gateway dependencies:
  → auth      [http://auth.internal:8080]         ❌  UNHEALTHY
  → database  [postgres://db.internal:5432]       ❌  POOL EXHAUSTED
  → payment   [http://payment.internal:8080]      ⚠️   DEGRADED
  → cache     [redis://cache.internal:6379]       ⚠️   DEGRADED
  → analytics [internal — no direct dependency]   ✅  (not a direct dep)

All upstream services that depend on database are affected.
""",
        "auth": """\
auth dependencies:
  → database  [postgres://db.internal:5432]  ❌  POOL EXHAUSTED
  → cache     [redis://cache.internal:6379]  ⚠️   DEGRADED

Auth has NO dependency on API (it IS upstream of API).
Auth degradation is caused directly by database pool exhaustion.
""",
        "payment": """\
payment dependencies:
  → database  [postgres://db.internal:5432]  ❌  POOL EXHAUSTED (fallback to cache)
  → cache     [redis://cache.internal:6379]  ⚠️   DEGRADED (partially available)

Payment has a read-only cache fallback — this is why it's degraded, not down.
""",
        "database": """\
database upstream dependencies: none (root data layer)
Downstream consumers:
  → api       ← FAILING (no connections)
  → auth      ← FAILING (no connections)
  → payment   ← FAILING (no connections, using cache fallback)
  → analytics ← HOLDING 100/100 connections (root cause)
""",
        "analytics": """\
analytics dependencies:
  → database  [postgres://db.internal:5432]  ⚠️  HOLDING 100/100 connections

analytics is a CONSUMER of the database, not upstream of any affected service.
It does NOT appear in the alert graph — it's the silent cause.
""",
        "cache": """\
cache dependencies: none (uses memory only)
Downstream consumers: api, auth, payment
Cache is NOT the root cause — hit rate drop is a symptom.
""",
    }

    _CONFIGS = {
        "api": """\
Recent config changes for api-gateway:
  14:15:00 UTC — Deploy v3.2.1 by ci-bot
    Changes: Updated OAuth2 token refresh logic, dependency version bumps
    Health checks: All green post-deploy (verified at 14:20, 14:30, 14:40 UTC)
    Note: This deployment is healthy — it is NOT the cause of the incident.

  13:00:00 UTC — Config: Rate limit thresholds updated (no issues)
""",
        "database": """\
Recent config changes for database:
  No config changes in last 48 hours.

  ACTIVE SESSION of note:
  14:44:30 UTC — analytics_pipeline connected (PID 8847)
  Query: SELECT * FROM events WHERE date >= '2020-01-01'
  No connection limit configured for analytics user.
  No query timeout configured.
""",
        "analytics": """\
Recent config changes for analytics:
  14:44:20 UTC — Job triggered: weekly_event_aggregation (scheduled job)
  Config: No connection_limit set, no query_timeout set, no circuit breaker

  Known issue: analytics jobs have always run against the production database
  with no connection pooling limits. This is a long-standing configuration risk.
""",
        "auth": """\
Recent config changes for auth:
  No changes in last 4 hours.
  Memory at 78% is within normal operating parameters.
""",
    }

    # ── Accepted answers ───────────────────────────────────────────────────────

    CORRECT_ROOT_CAUSES = frozenset({
        "db_connection_pool_exhausted",
        "database_connection_pool_exhausted",
        "connection_pool_exhaustion",
        "runaway_query",
        "analytics_query",
        "runaway_analytics_query",
        "db_pool_exhausted",
        "database_pool_exhausted",
    })

    # These are the red herring wrong answers that the scenario anticipates
    RED_HERRING_CAUSES = frozenset({
        "api_deployment",
        "bad_deploy",
        "deploy_issue",
        "api_deploy",
        "memory_pressure",
        "auth_memory",
        "cache_failure",
        "cache_miss",
    })

    # ── Per-episode state ──────────────────────────────────────────────────────

    def _reset_scenario_state(self) -> None:
        self._done_investigations: set[str] = set()
        self._query_killed: bool = False
        self._pool_scaled: bool = False

    # ── Step dispatch ─────────────────────────────────────────────────────────

    def step(self, command: ParsedCommand) -> StepOutcome:
        action = command.action_type

        if action == "query_logs":
            return self._handle_query_logs(command)
        elif action == "check_metrics":
            return self._handle_check_metrics(command)
        elif action == "check_deps":
            return self._handle_check_deps(command)
        elif action == "check_config":
            return self._handle_check_config(command)
        elif action == "diagnose":
            return self._handle_diagnose(command)
        elif action == "kill_query":
            return self._handle_kill_query(command)
        elif action == "scale_resource":
            return self._handle_scale_resource(command)
        elif action == "restart_service":
            return self._handle_restart_service(command)
        elif action == "rollback_deploy":
            return self._handle_rollback_deploy(command)
        elif action == "escalate":
            return self._handle_escalate(command)
        else:
            return self._handle_unknown_command(command.raw)

    def get_initial_observation_text(self) -> str:
        return ""

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _handle_query_logs(self, command: ParsedCommand) -> StepOutcome:
        service = get_service_param(command.params, default="api")
        logs = self._LOGS.get(service)

        if logs is None:
            score = self._score_event("invalid_input")
            return StepOutcome(
                investigation_result=f"No log data for service '{service}'.",
                reward=score.reward,
                done=self.is_done(),
                incident_resolved=self._incident_resolved,
                root_cause_identified=self._root_cause_identified,
            )

        key = f"logs:{service}"
        duplicate = key in self._done_investigations
        if not duplicate:
            self._done_investigations.add(key)

        if service == "api":
            event = "investigation.query_logs.api"
        elif service == "database":
            event = "investigation.query_logs.database"
        elif service == "analytics":
            event = "investigation.query_logs.analytics"
        else:
            event = "investigation.query_logs.default"
        score = self._score_event(event, duplicate=duplicate)

        return StepOutcome(
            investigation_result=logs,
            reward=score.reward,
            done=self.is_done(),
            incident_resolved=self._incident_resolved,
            root_cause_identified=self._root_cause_identified,
        )

    def _handle_check_metrics(self, command: ParsedCommand) -> StepOutcome:
        service = get_service_param(command.params, default="database")
        metric = get_metric_param(command.params, default="connections")
        data = self._METRICS.get((service, metric))

        if data is None:
            score = self._score_event("invalid_input")
            return StepOutcome(
                investigation_result=(
                    f"No metric '{metric}' for service '{service}'.\n"
                    "Available: error_rate, latency_p95, connections, memory, cpu, "
                    "throughput, cache_hit_rate"
                ),
                reward=score.reward,
                done=self.is_done(),
                incident_resolved=self._incident_resolved,
                root_cause_identified=self._root_cause_identified,
            )

        key = f"metric:{service}:{metric}"
        duplicate = key in self._done_investigations
        if not duplicate:
            self._done_investigations.add(key)

        if service == "database" and metric == "connections":
            event = "investigation.check_metrics.database.connections"
        else:
            event = "investigation.check_metrics.default"
        score = self._score_event(event, duplicate=duplicate)

        return StepOutcome(
            investigation_result=data,
            reward=score.reward,
            done=self.is_done(),
            incident_resolved=self._incident_resolved,
            root_cause_identified=self._root_cause_identified,
        )

    def _handle_check_deps(self, command: ParsedCommand) -> StepOutcome:
        service = get_service_param(command.params, default="api")
        data = self._DEPS.get(service, f"No dependency data for '{service}'.")

        key = f"deps:{service}"
        duplicate = key in self._done_investigations
        if not duplicate:
            self._done_investigations.add(key)

        event = (
            "investigation.check_deps.core"
            if service in ("api", "auth", "payment")
            else "investigation.check_deps.default"
        )
        score = self._score_event(event, duplicate=duplicate)

        return StepOutcome(
            investigation_result=data,
            reward=score.reward,
            done=self.is_done(),
            incident_resolved=self._incident_resolved,
            root_cause_identified=self._root_cause_identified,
        )

    def _handle_check_config(self, command: ParsedCommand) -> StepOutcome:
        service = get_service_param(command.params, default="api")
        data = self._CONFIGS.get(service, f"No config history for '{service}'.")

        key = f"config:{service}"
        duplicate = key in self._done_investigations
        if not duplicate:
            self._done_investigations.add(key)

        if service == "database":
            event = "investigation.check_config.database"
        elif service == "analytics":
            event = "investigation.check_config.analytics"
        else:
            event = "investigation.check_config.default"
        score = self._score_event(event, duplicate=duplicate)

        return StepOutcome(
            investigation_result=data,
            reward=score.reward,
            done=self.is_done(),
            incident_resolved=self._incident_resolved,
            root_cause_identified=self._root_cause_identified,
        )

    def _handle_diagnose(self, command: ParsedCommand) -> StepOutcome:
        raw = command.params.get("root_cause", "").lower().strip()
        normalised = raw.replace("-", "_").replace(" ", "_")

        if normalised in self.CORRECT_ROOT_CAUSES:
            self._root_cause_identified = True
            score = self._score_event("diagnosis.correct")
            return StepOutcome(
                investigation_result=(
                    "✅ Correct diagnosis!\n\n"
                    "Root cause confirmed: The analytics pipeline launched a full-table "
                    "scan with no connection limit or query timeout at 14:44 UTC. It acquired "
                    "all 100 database connections, leaving none for api, auth, or payment.\n\n"
                    "Immediate action: kill the runaway query (kill_query service=database query_id=runaway_analytics)\n"
                    "Secondary action: scale the connection pool (scale_resource service=database resource=connection_pool)"
                ),
                reward=score.reward,
                done=self.is_done(),
                incident_resolved=False,
                root_cause_identified=True,
            )
        elif normalised in self.RED_HERRING_CAUSES:
            score = self._score_event("diagnosis.wrong", premature=True)
            if "api_deployment" in normalised or "deploy" in normalised:
                detail = (
                    "❌ Incorrect diagnosis: the API deployment at 14:15 UTC has been "
                    "healthy for 30+ minutes with clean post-deploy checks. API errors "
                    "started at 14:46 — 31 minutes after the deployment. Not the cause.\n\n"
                    "Hint: What do api, auth, and payment all have in common?"
                )
            elif "memory" in normalised:
                detail = (
                    "❌ Incorrect diagnosis: auth memory at 78% is within normal operating "
                    "parameters (threshold: 90%). Memory is not causing the authentication "
                    "failures — those failures started when the DB connection pool was exhausted.\n\n"
                    "Hint: check the database metrics directly."
                )
            else:
                detail = f"❌ Incorrect diagnosis: '{raw}'. The evidence doesn't support this conclusion."

            return StepOutcome(
                investigation_result=detail,
                reward=score.reward,
                done=self.is_done(),
                incident_resolved=False,
                root_cause_identified=False,
            )
        else:
            score = self._score_event("diagnosis.wrong", premature=True)
            return StepOutcome(
                investigation_result=(
                    f"❌ Incorrect diagnosis: '{raw}'.\n"
                    "Review the database metrics and logs — the common dependency "
                    "between all affected services is the key."
                ),
                reward=score.reward,
                done=self.is_done(),
                incident_resolved=False,
                root_cause_identified=False,
            )

    def _handle_kill_query(self, command: ParsedCommand) -> StepOutcome:
        service = get_service_param(command.params, default="database")
        query_id = command.params.get("query_id", "").lower().strip()

        if service != "database":
            score = self._score_event("remediation.wrong", destructive=True)
            return StepOutcome(
                investigation_result=f"kill_query: service '{service}' doesn't support this command.",
                reward=score.reward,
                done=self.is_done(),
                incident_resolved=False,
                root_cause_identified=self._root_cause_identified,
            )

        # Accept any query_id that suggests the runaway analytics query
        analytics_ids = {"runaway_analytics", "8847", "analytics", "analytics_pipeline",
                         "weekly_event_aggregation", "runaway", "8847pid"}
        query_id_norm = query_id.replace("-", "_").replace(" ", "_")

        if query_id_norm in analytics_ids or "analytic" in query_id_norm or "runway" in query_id_norm:
            self._query_killed = True
            # If pool was already scaled AND query killed, resolve
            done_now = self._pool_scaled  # fully resolved only if both done
            if done_now:
                self._incident_resolved = True
                self._current_system_status = {k: "healthy" for k in self._current_system_status}

            score = self._score_event(
                "remediation.kill_query.database",
                resolved=done_now,
            )

            return StepOutcome(
                investigation_result=(
                    "✅ Runaway query killed.\n\n"
                    f"PID 8847 (analytics_pipeline) terminated.\n"
                    "- Database connection pool: 100/100 → 0/100 (all connections freed)\n"
                    "- api connections: recovering (errors dropping)\n"
                    "- auth connections: recovering (timeouts clearing)\n"
                    "- payment: recovering\n\n"
                    + (
                        "Incident fully resolved. Services recovering to healthy state."
                        if done_now else
                        "Services are recovering. Consider scaling the connection pool to prevent recurrence:\n"
                        "  scale_resource service=database resource=connection_pool"
                    )
                ),
                reward=score.reward,
                done=done_now,
                incident_resolved=done_now,
                root_cause_identified=self._root_cause_identified,
            )
        else:
            # Wrong query ID but right service — no reward, no penalty
            score = self._score_event("invalid_input")
            return StepOutcome(
                investigation_result=(
                    f"Query '{query_id}' not found or already completed.\n"
                    "Active long-running queries on database:\n"
                    "  PID 8847 | analytics_pipeline | 4m 12s | SELECT * FROM events (full scan)\n\n"
                    "Hint: kill_query service=database query_id=runaway_analytics"
                ),
                reward=score.reward,
                done=self.is_done(),
                incident_resolved=False,
                root_cause_identified=self._root_cause_identified,
            )

    def _handle_scale_resource(self, command: ParsedCommand) -> StepOutcome:
        service = get_service_param(command.params, default="database")
        resource = command.params.get("resource", "").lower().strip()

        if service == "database" and resource in ("connection_pool", "connections", "pool", "db_connections"):
            self._pool_scaled = True
            done_now = self._query_killed  # only resolve if both done
            if done_now:
                self._incident_resolved = True
                self._current_system_status = {k: "healthy" for k in self._current_system_status}

            score = self._score_event(
                "remediation.scale_resource.database.connection_pool",
                resolved=done_now,
            )

            return StepOutcome(
                investigation_result=(
                    "✅ Database connection pool scaled.\n\n"
                    "Connection pool: 100 → 200 (doubled)\n"
                    "- Future analytics jobs can now use up to 50 connections without impacting production\n"
                    "- Production services guaranteed minimum 150 connections\n\n"
                    + (
                        "Incident fully resolved. All services recovered to healthy state."
                        if done_now else
                        "Pool scaled. To fully resolve: kill the runaway query still holding connections:\n"
                        "  kill_query service=database query_id=runaway_analytics"
                    )
                ),
                reward=score.reward,
                done=done_now,
                incident_resolved=done_now,
                root_cause_identified=self._root_cause_identified,
            )
        else:
            score = self._score_event("remediation.wrong", destructive=True)
            return StepOutcome(
                investigation_result=(
                    f"scale_resource: '{resource}' on '{service}' had no effect on the incident.\n"
                    "The bottleneck is the database connection pool.\n"
                    "Try: scale_resource service=database resource=connection_pool"
                ),
                reward=score.reward,
                done=self.is_done(),
                incident_resolved=False,
                root_cause_identified=self._root_cause_identified,
            )

    def _handle_restart_service(self, command: ParsedCommand) -> StepOutcome:
        service = get_service_param(command.params)
        score = self._score_event("remediation.wrong", destructive=True)
        return StepOutcome(
            investigation_result=(
                f"⚠️ Restarted '{service}', but it immediately begins failing again.\n"
                "The database connection pool is still exhausted — restarting application "
                "services doesn't fix the underlying database bottleneck.\n\n"
                "Hint: The root problem is in the database layer, not in application services."
            ),
            reward=score.reward,
            done=self.is_done(),
            incident_resolved=False,
            root_cause_identified=self._root_cause_identified,
        )

    def _handle_rollback_deploy(self, command: ParsedCommand) -> StepOutcome:
        service = get_service_param(command.params)
        if service == "api":
            message = (
                "⚠️ API deployment v3.2.1 rolled back to v3.2.0. "
                "But api, auth, and payment are still failing — the deployment wasn't the cause.\n"
                "The database connection pool is still exhausted.\n\n"
                "Note: The deployment had been running healthy for 30+ minutes before this incident."
            )
        else:
            message = (
                f"⚠️ Rolled back '{service}' but the incident continues. "
                "The deployment was not the root cause."
            )
        score = self._score_event("remediation.wrong", destructive=True)
        return StepOutcome(
            investigation_result=message,
            reward=score.reward,
            done=self.is_done(),
            incident_resolved=False,
            root_cause_identified=self._root_cause_identified,
        )

    def _handle_escalate(self, command: ParsedCommand) -> StepOutcome:
        reason = command.params.get("reason", "")
        num_investigations = len(self._done_investigations)

        if num_investigations >= 3:
            self._incident_resolved = True
            score = self._score_event("escalation.with_evidence", resolved=True)
            return StepOutcome(
                investigation_result=(
                    f"✅ Escalated with evidence to on-call lead.\n\n"
                    f"Reason: {reason}\n"
                    f"Evidence gathered: {num_investigations} investigation(s)\n\n"
                    "On-call lead will drive resolution with full context provided."
                ),
                reward=score.reward,
                done=True,
                incident_resolved=True,
                root_cause_identified=self._root_cause_identified,
            )
        else:
            score = self._score_event("escalation.no_evidence", premature=True)
            return StepOutcome(
                investigation_result=(
                    f"⚠️ Escalated without sufficient evidence ({num_investigations} investigation(s), need ≥3).\n"
                    "On-call lead will have to start from scratch.\n\n"
                    "Tip: gather evidence from multiple services before escalating a P1."
                ),
                reward=score.reward,
                done=True,
                incident_resolved=False,
                root_cause_identified=self._root_cause_identified,
            )
