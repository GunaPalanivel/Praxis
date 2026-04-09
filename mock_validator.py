"""
Local mock validator for strict reward-bound edge cases.

This script simulates the same output surface the remote validator is expected
to parse: [STEP] and [END] lines emitted by inference.run_episode().

It forces boundary inputs (raw 0.0 and raw 1.0 rewards) and an exception path,
then verifies emitted reward text stays strictly inside (0, 1) for the current
two-decimal output contract.
"""

from __future__ import annotations

import asyncio
import io
import re
import sys
from contextlib import redirect_stdout

import inference


class _FakeStepResult:
    def __init__(self, observation, reward: float, done: bool, info: dict | None = None):
        self.observation = observation
        self.reward = reward
        self.done = done
        self.info = info or {}


def _make_observation(step_number: int):
    return inference.PraxisObservation(
        alert_summary="Synthetic test alert",
        system_status={"auth": "critical"},
        investigation_result="Synthetic investigation output",
        available_commands=["query_logs service=<name> timerange=<N>m"],
        time_elapsed_minutes=float(step_number * 2.5),
        severity="P2",
        services_affected=["auth"],
        step_number=step_number,
    )


class _FakeEnv:
    def __init__(self, *, reward: float | None = None, raise_on_step: bool = False):
        self._reward = reward
        self._raise_on_step = raise_on_step
        self._step_count = 0

    async def reset(self, task_name: str = "single-service-alert"):
        self._step_count = 0
        return _make_observation(step_number=0)

    async def step(self, action):
        if self._raise_on_step:
            raise RuntimeError("simulated_step_failure")

        self._step_count += 1
        return _FakeStepResult(
            observation=_make_observation(step_number=self._step_count),
            reward=float(self._reward if self._reward is not None else 0.5),
            done=True,
            info={},
        )

    async def close(self):
        return None


def _parse_step_rewards(stdout_text: str) -> list[float]:
    return [
        float(match.group(1))
        for match in re.finditer(r"^\[STEP\].*? reward=(\d+\.\d{2}) ", stdout_text, re.MULTILINE)
    ]


def _parse_end_rewards(stdout_text: str) -> list[float]:
    match = re.search(r"^\[END\].*rewards=([^\n]*)$", stdout_text, re.MULTILINE)
    if not match:
        return []

    rewards_csv = match.group(1).strip()
    if not rewards_csv:
        return []

    return [float(item) for item in rewards_csv.split(",") if item]


async def _run_case(name: str, fake_env: _FakeEnv, expected_reward: float) -> tuple[bool, str]:
    original_from_url = inference.PraxisEnv.from_url

    async def _fake_from_url(cls, url: str, timeout: float = 30.0):
        return fake_env

    inference.PraxisEnv.from_url = classmethod(_fake_from_url)
    output_buffer = io.StringIO()

    try:
        with redirect_stdout(output_buffer):
            episode_result = await inference.run_episode("single-service-alert", client=None)
    except Exception as exc:
        return False, f"{name}: crashed with exception: {exc}"
    finally:
        inference.PraxisEnv.from_url = original_from_url

    emitted = output_buffer.getvalue()
    step_rewards = _parse_step_rewards(emitted)
    end_rewards = _parse_end_rewards(emitted)

    if not step_rewards:
        return False, f"{name}: no [STEP] rewards emitted\n{emitted}"
    if not end_rewards:
        return False, f"{name}: no [END] rewards emitted\n{emitted}"

    if any(value <= 0.0 or value >= 1.0 for value in step_rewards + end_rewards):
        return False, f"{name}: strict bounds violated in emitted rewards: steps={step_rewards}, end={end_rewards}"

    if any(abs(value - expected_reward) > 1e-9 for value in step_rewards):
        return False, f"{name}: step rewards {step_rewards} did not match expected {expected_reward:.2f}"

    if any(abs(value - expected_reward) > 1e-9 for value in end_rewards):
        return False, f"{name}: END rewards {end_rewards} did not match expected {expected_reward:.2f}"

    if any(abs(value - expected_reward) > 1e-9 for value in episode_result.rewards):
        return False, f"{name}: EpisodeResult rewards {episode_result.rewards} did not match expected {expected_reward:.2f}"

    if "reward=0.00" in emitted or "reward=1.00" in emitted:
        return False, f"{name}: emitted forbidden rounded boundary value in STEP lines\n{emitted}"

    return True, f"{name}: PASS (expected {expected_reward:.2f})"


async def _main() -> int:
    print("Starting local mock validator for strict edge-case bounds...\n")

    cases = [
        ("raw_zero_reward", _FakeEnv(reward=0.0), 0.01),
        ("raw_one_reward", _FakeEnv(reward=1.0), 0.99),
        ("step_exception_fallback", _FakeEnv(raise_on_step=True), 0.01),
    ]

    all_passed = True
    for name, env, expected in cases:
        ok, message = await _run_case(name, env, expected)
        print(message)
        all_passed = all_passed and ok

    print("\n" + "=" * 60)
    if all_passed:
        print("SUCCESS: mock validator passed. Boundary clipping is active.")
        return 0

    print("FAILURE: mock validator found a strict-bound leak.")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
