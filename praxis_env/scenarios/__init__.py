"""
praxis_env.scenarios — Scenario registry and base classes.

Each scenario is a self-contained, deterministic state machine representing
a specific production incident. Scenarios are loaded by the environment
server during reset() and stepped through during the episode.
"""

from praxis_env.scenarios.base import BaseScenario

# Populated in later phases as scenarios are implemented
SCENARIO_REGISTRY: dict[str, type[BaseScenario]] = {}


def get_scenario(task_name: str) -> BaseScenario:
    """
    Instantiate a registered scenario by task name.

    Args:
        task_name: One of the registered scenario names

    Returns:
        A fresh, initialised BaseScenario instance

    Raises:
        ValueError: if task_name is not registered
    """
    if task_name not in SCENARIO_REGISTRY:
        available = ", ".join(sorted(SCENARIO_REGISTRY.keys()))
        raise ValueError(
            f"Unknown task: '{task_name}'. "
            f"Available tasks: [{available}]"
        )
    return SCENARIO_REGISTRY[task_name]()


def list_tasks() -> list[str]:
    """Return sorted list of all registered task names."""
    return sorted(SCENARIO_REGISTRY.keys())
