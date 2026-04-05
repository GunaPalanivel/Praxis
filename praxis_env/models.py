"""
praxis_env.models — Data models for Praxis environment.

Uses Python dataclasses (not Pydantic) to match the OpenEnv scaffold pattern.
All models are fully typed with Python 3.11+ type hints.

Design Decisions:
  - dataclass over Pydantic: matches openenv-core's create_fastapi_app() expectations
  - field() with default_factory for mutable defaults (list, dict)
  - No Optional where possible — every field should have a defined value
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedCommand:
    """Structured representation of a parsed action command string."""

    action_type: str
    params: dict[str, str] = field(default_factory=dict)
    raw: str = ""


@dataclass
class StepOutcome:
    """
    Internal result from a scenario processing a command.
    Converted to HTTP response by the environment server.
    """

    investigation_result: str
    reward: float
    done: bool
    incident_resolved: bool
    root_cause_identified: bool
    info: dict[str, Any] = field(default_factory=dict)



@dataclass
class PraxisAction:
    """
    What the agent sends to the environment each step.

    The action is a single command string that the environment parses
    into a structured operation. This design is LLM-friendly: the model
    generates natural text commands rather than structured JSON.

    Command grammar:
        query_logs service=<name> timerange=<N>m
        check_metrics service=<name> metric=<type>
        check_deps service=<name>
        check_config service=<name>
        diagnose root_cause=<cause>
        restart_service service=<name>
        rollback_deploy service=<name>
        scale_resource service=<name> resource=<type> [value=<N>]
        kill_query service=<name> query_id=<id>
        escalate reason=<text>

    Example:
        PraxisAction(command="query_logs service=auth timerange=5m")
        PraxisAction(command="diagnose root_cause=bad_config")
        PraxisAction(command="rollback_deploy service=auth")
    """

    command: str


@dataclass
class PraxisObservation:
    """
    What the agent receives after each action (or from reset()).

    Provides rich, text-based information that an LLM can reason about
    to decide the next action. Every field is always populated — no Nones.

    Fields:
        alert_summary:          Current incident description (markdown-formatted)
        system_status:          Service name → health status map
                                Status values: "healthy" | "degraded" | "critical" | "down"
        investigation_result:   Output of the last command (logs, metrics, dep graph, etc.)
                                Empty string on reset() (no previous command)
        available_commands:     List of valid command templates the agent can use
        time_elapsed_minutes:   Float minutes since incident started (increases each step)
        severity:               Incident severity: "P0" | "P1" | "P2" | "P3"
        services_affected:      List of services currently showing issues
        step_number:            Current step count (0 on reset, increments with each step)
    """

    alert_summary: str
    system_status: dict[str, str]
    investigation_result: str
    available_commands: list[str]
    time_elapsed_minutes: float
    severity: str
    services_affected: list[str]
    step_number: int


@dataclass
class PraxisState:
    """
    Episode metadata exposed via the state() endpoint.

    Provides a lightweight snapshot of what's happening without the
    full observation payload. Useful for monitoring and debugging.

    Fields:
        episode_id:             Unique identifier for this episode (task_name + counter)
        step_count:             How many steps have been taken in this episode
        task_name:              The active scenario name
        incident_resolved:      True when the incident has been correctly remediated
        root_cause_identified:  True when agent has issued a correct diagnose command
        cumulative_reward:      Sum of rewards so far (for monitoring only)
    """

    episode_id: str
    step_count: int
    task_name: str
    incident_resolved: bool = False
    root_cause_identified: bool = False
    cumulative_reward: float = 0.0


# ────────────────────────────────────────────────────────────────────────────
# Available commands advertised to the agent
# ────────────────────────────────────────────────────────────────────────────

AVAILABLE_COMMANDS: list[str] = [
    "query_logs service=<name> timerange=<N>m",
    "check_metrics service=<name> metric=<type>",
    "check_deps service=<name>",
    "check_config service=<name>",
    "diagnose root_cause=<cause>",
    "restart_service service=<name>",
    "rollback_deploy service=<name>",
    "scale_resource service=<name> resource=<type>",
    "kill_query service=<name> query_id=<id>",
    "escalate reason=<text>",
]

VALID_METRICS: frozenset[str] = frozenset({
    "error_rate",
    "latency_p95",
    "throughput",
    "connections",
    "memory",
    "cpu",
    "resolution_failures",
    "cache_hit_rate",
})

VALID_SEVERITIES: frozenset[str] = frozenset({"P0", "P1", "P2", "P3"})

VALID_SERVICE_STATUSES: frozenset[str] = frozenset({
    "healthy",
    "degraded",
    "critical",
    "down",
})
