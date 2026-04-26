from __future__ import annotations

import math
import random
import time

import matplotlib.pyplot as plt
import numpy as np
import requests


PRAXIS_BASE_URL = "https://gp5901-praxis.hf.space"
TASK_NAME = "single-service-alert"
SEED = 42

random.seed(SEED)
np.random.seed(SEED)

ACTION_POOL = [
    "query_logs service=auth timerange=5m",
    "check_metrics service=auth metric=error_rate",
    "check_config service=auth",
    "diagnose root_cause=bad_config",
    "restart_service service=auth",
    "rollback_deploy service=auth",
    "escalate reason=need_senior_support",
]


def api_post(path: str, payload: dict, headers: dict | None = None) -> dict:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{PRAXIS_BASE_URL}{path}",
                json=payload,
                headers=headers or {},
                timeout=20,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: PERF203
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"API call failed for {path}: {last_error}")


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits)
    exp_values = np.exp(shifted)
    return exp_values / np.sum(exp_values)


def run_episode_with_policy(
    logits: np.ndarray, max_steps: int = 5
) -> tuple[list[float], list[int]]:
    reset_payload = api_post("/reset", {"task_name": TASK_NAME})
    sid = reset_payload.get("session_id", "")
    headers = {"x-session-id": sid} if sid else {}

    rewards: list[float] = []
    chosen_idxs: list[int] = []
    for _ in range(max_steps):
        probs = softmax(logits)
        idx = int(np.random.choice(len(ACTION_POOL), p=probs))
        command = ACTION_POOL[idx]
        step_payload = api_post("/step", {"command": command}, headers=headers)
        rewards.append(float(step_payload["reward"]))
        chosen_idxs.append(idx)
        if bool(step_payload["done"]):
            break
    return rewards, chosen_idxs


def evaluate_policy(
    logits: np.ndarray, episodes: int = 8, max_steps: int = 5
) -> list[float]:
    means: list[float] = []
    for _ in range(episodes):
        rewards, _ = run_episode_with_policy(logits, max_steps=max_steps)
        if rewards:
            means.append(float(np.mean(rewards)))
    return means


def main() -> None:
    baseline_logits = np.zeros(len(ACTION_POOL), dtype=np.float64)
    baseline_rewards = evaluate_policy(baseline_logits, episodes=8, max_steps=5)

    episodes = 12
    group_size = 3
    max_steps = 5
    lr = 0.08

    policy_logits = np.zeros(len(ACTION_POOL), dtype=np.float64)
    loss_curve: list[float] = []

    for episode_idx in range(episodes):
        group_returns: list[float] = []
        group_actions: list[list[int]] = []
        for _ in range(group_size):
            rewards, chosen_idxs = run_episode_with_policy(
                policy_logits, max_steps=max_steps
            )
            ep_return = float(np.mean(rewards)) if rewards else 0.01
            group_returns.append(ep_return)
            group_actions.append(chosen_idxs)

        returns_arr = np.array(group_returns, dtype=np.float64)
        baseline = float(np.mean(returns_arr))
        std = float(np.std(returns_arr) + 1e-8)
        advantages = (returns_arr - baseline) / std

        probs = softmax(policy_logits)
        grad = np.zeros_like(policy_logits)
        loss = 0.0
        action_count = 0

        for adv, actions in zip(advantages, group_actions):
            for act in actions:
                one_hot = np.zeros_like(policy_logits)
                one_hot[act] = 1.0
                grad += adv * (one_hot - probs)
                loss += -adv * math.log(max(probs[act], 1e-8))
                action_count += 1

        denom = max(1, action_count)
        grad /= denom
        loss /= denom
        policy_logits += lr * grad
        loss_curve.append(float(loss))
        print(
            f"episode {episode_idx + 1}/{episodes} mean_return={baseline:.4f} loss={loss:.4f}",
            flush=True,
        )

    trained_rewards = evaluate_policy(policy_logits, episodes=8, max_steps=5)

    x_baseline = np.arange(1, len(baseline_rewards) + 1)
    x_trained = np.arange(1, len(trained_rewards) + 1)

    plt.figure(figsize=(10, 5))
    plt.plot(x_baseline, baseline_rewards, color="red", label="Untrained Baseline")
    plt.plot(x_trained, trained_rewards, color="green", label="Trained Agent")
    plt.xlabel("Training Step / Episode")
    plt.ylabel("Mean Episode Reward")
    plt.title("Praxis Reward Comparison: Baseline vs Trained")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("reward_curve.png", dpi=150)
    plt.close()

    plt.figure(figsize=(10, 5))
    plt.plot(
        np.arange(1, len(loss_curve) + 1),
        loss_curve,
        color="blue",
        label="Training Loss",
    )
    plt.xlabel("Training Step / Episode")
    plt.ylabel("Loss")
    plt.title("GRPO Training Loss Curve")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("loss_curve.png", dpi=150)
    plt.close()

    print("Saved reward_curve.png and loss_curve.png")


if __name__ == "__main__":
    main()
