# Contributing to Praxis

We welcome contributions — new scenarios, bug fixes, documentation improvements, and reward function enhancements.

## Development Setup

```bash
git clone https://github.com/your-org/praxis-env
cd praxis-env
pip install -e ".[dev]"
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_models.py -v

# With coverage report
pytest tests/ --cov=praxis_env --cov=server --cov-report=term-missing
```

## Project Structure

```
praxis_env/          ← Environment package (imported by inference.py)
  models.py          ← Dataclass models — PraxisAction, PraxisObservation, PraxisState
  client.py          ← HTTP client for connecting to the server
  scenarios/
    base.py          ← BaseScenario abstract class
    *.py             ← Individual scenario implementations

server/              ← FastAPI server (runs in Docker container)
  praxis_environment.py  ← Core reset/step/state logic
  app.py             ← HTTP routes and middleware
  reward.py          ← Reward calculator (added in Phase 6)
  command_parser.py  ← Command string parser (added in Phase 2)

tests/               ← pytest test suite
docs/                ← This documentation
```

## Adding a New Scenario

1. Create `praxis_env/scenarios/your_scenario.py` — subclass `BaseScenario`
2. Implement: `_reset_scenario_state()`, `step()`, `get_initial_observation_text()`
3. Register in `praxis_env/scenarios/__init__.py`
4. Write tests: determinism check (3× same actions), reward bounds check

**Quick template:**
```python
from praxis_env.scenarios.base import BaseScenario, ParsedCommand, StepOutcome

class YourScenario(BaseScenario):
    NAME = "your-scenario-name"
    SEVERITY = "P2"
    MAX_STEPS = 15
    ALERT_SUMMARY = "## 🚨 Your incident description"
    INITIAL_SYSTEM_STATUS = {"service-a": "critical"}
    INITIAL_AFFECTED_SERVICES = ["service-a"]

    def _reset_scenario_state(self) -> None:
        self._investigations_done: set = set()

    def step(self, command: ParsedCommand) -> StepOutcome:
        if command.action_type == "query_logs":
            return StepOutcome(
                investigation_result="Log output here",
                reward=self.clamp_reward(0.05),
                done=self.is_done(),
                incident_resolved=self._incident_resolved,
                root_cause_identified=self._root_cause_identified,
            )
        return self._handle_unknown_command(command.raw)

    def get_initial_observation_text(self) -> str:
        return ""
```

## Code Standards

- **No randomness** — scenarios must be fully deterministic
- **Typed** — all functions and class variables have type hints
- **No crashes on bad input** — `step()` must handle any string gracefully
- **Rewards clamped** — always use `self.clamp_reward(value)` before returning

## Pull Request Checklist

- [ ] New scenario follows `BaseScenario` contract
- [ ] `SCENARIO_REGISTRY` updated in `scenarios/__init__.py`
- [ ] Tests added: optimal path score, determinism (3×), reward bounds
- [ ] `pytest tests/ -v` passes with no failures
- [ ] No hardcoded secrets
