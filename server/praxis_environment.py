"""
server.praxis_environment — Core environment logic.

This module implements the Environment interface expected by openenv-core.
It is loaded by server/app.py and mounted into the FastAPI application.

Command parsing is delegated to server.command_parser — this module never
does raw string parsing itself.

Flow:
    POST /reset  → praxis_environment.reset() → PraxisObservation
    POST /step   → praxis_environment.step()  → StepResult
    GET  /state  → praxis_environment.state() → PraxisState

The environment delegates all scenario-specific logic to the active
BaseScenario instance (loaded from the scenario registry on reset).

Design choices:
    - The environment is stateful: one active scenario per server instance
    - Thread safety: single-threaded sequential steps (not concurrent)
    - Episode ID: generated as "{task_name}_{count}" for deterministic tracing
"""

from __future__ import annotations

import logging
from typing import Any

from praxis_env.models import (
    PraxisAction,
    PraxisObservation,
    PraxisState,
    ensure_ascii_text,
)
from praxis_env.scenarios import get_scenario, list_tasks
from praxis_env.scenarios.base import BaseScenario, StepOutcome
from server.command_parser import parse_command

logger = logging.getLogger(__name__)


class PraxisEnvironment:
    """
    Stateful environment controller.

    Manages one active scenario at a time. The scenario tracks all
    episode state; this class is responsible for:
      - Parsing commands from PraxisAction
      - Routing commands to the active scenario
      - Serialising scenario outcomes back to OpenEnv types

    Usage (in server/app.py):
        env = PraxisEnvironment()
        obs = env.reset(task_name="single-service-alert")
        result = env.step(PraxisAction(command="query_logs service=auth timerange=5m"))
        state = env.state()
    """

    def __init__(self) -> None:
        self._scenario: BaseScenario | None = None
        self._episode_count: int = 0

    # ── Public API (called by FastAPI routes) ─────────────────────────────────

    def reset(self, task_name: str = "single-service-alert") -> PraxisObservation:
        """
        Start a new episode with the named scenario.

        Args:
            task_name: Scenario to load (see list_tasks() for options).

        Returns:
            Initial PraxisObservation with the incident alert and system status.

        Raises:
            ValueError: if task_name is not registered.
        """
        self._episode_count += 1
        episode_id = f"{task_name}_{self._episode_count}"

        logger.info("reset() → episode_id=%s task=%s", episode_id, task_name)

        self._scenario = get_scenario(task_name)
        self._scenario.reset(episode_id=episode_id)

        obs = self._scenario.get_observation()
        # Override investigation_result with scenario's initial text
        obs.investigation_result = ensure_ascii_text(
            self._scenario.get_initial_observation_text()
        )
        return obs

    def step(self, action: PraxisAction) -> dict[str, Any]:
        """
        Execute one action and return the raw result dict.

        Args:
            action: PraxisAction with a command string.

        Returns:
            Dict with keys: observation, reward, done, info
            (serialisable to JSON for the FastAPI response).

        Raises:
            RuntimeError: if called before reset().
        """
        if self._scenario is None:
            raise RuntimeError("step() called before reset(). Call reset() first.")

        logger.debug("step() → command=%r", action.command)

        # The environment owns step_count and cumulative reward bookkeeping.
        # Scenarios return domain outcomes without mutating those counters.
        # Parse command string -> structured ParsedCommand
        parsed = parse_command(action.command)

        # Delegate to active scenario
        outcome: StepOutcome = self._scenario.step(parsed)

        # Update scenario's investigation result for next observation
        self._scenario._last_investigation_result = outcome.investigation_result
        self._scenario._step_count += 1
        self._scenario._cumulative_reward += outcome.reward

        # Build the next observation
        obs = self._scenario.get_observation()
        # Override step_number to reflect the step just taken
        obs.step_number = self._scenario._step_count

        logger.debug(
            "step() → reward=%.3f done=%s step=%d",
            outcome.reward,
            outcome.done,
            obs.step_number,
        )

        return {
            "observation": self._obs_to_dict(obs),
            "reward": outcome.reward,
            "done": outcome.done or self._scenario.is_done(),
            "info": outcome.info,
        }

    def state(self) -> PraxisState:
        """
        Return current episode metadata without the full observation.

        Returns:
            PraxisState snapshot.

        Raises:
            RuntimeError: if called before reset().
        """
        if self._scenario is None:
            raise RuntimeError("state() called before reset(). Call reset() first.")
        return self._scenario.get_state()

    def list_tasks(self) -> list[str]:
        """Return all available task names."""
        return list_tasks()

    @staticmethod
    def _obs_to_dict(obs: PraxisObservation) -> dict[str, Any]:
        """Convert PraxisObservation to a JSON-serialisable dict."""
        return {
            "alert_summary": obs.alert_summary,
            "system_status": obs.system_status,
            "investigation_result": obs.investigation_result,
            "available_commands": obs.available_commands,
            "time_elapsed_minutes": obs.time_elapsed_minutes,
            "severity": obs.severity,
            "services_affected": obs.services_affected,
            "step_number": obs.step_number,
        }
