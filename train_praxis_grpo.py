#!/usr/bin/env python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "unsloth>=2024.10",
#   "trl>=0.13.0",
#   "transformers>=4.46.0",
#   "wandb>=0.18.0",
#   "trackio>=0.1.0",
#   "httpx>=0.27.0",
# ]
# ///
"""
MissionOps GRPO trainer (Issue #42).

Designed for two execution modes:
1) --smoke (local CPU/MPS): runs a short deterministic env loop and logs
   reward + per-rubric turn credit from /step.info.breakdown.
2) full training (GPU): runs TRL GRPO with optional Unsloth acceleration.
   Falls back to plain TRL path when Unsloth is unavailable.

TRL note: ``reward_func`` runs a full HTTP rollout per model completion. Each
non-empty line of the completion is executed as a command in order (same
session, after one ``reset``), up to ``--max-turns`` steps. If the model emits a
single line, behavior matches the former one-step contract. If the episode ends
with ``done=true`` and the server reports ``final_score`` on ``/state``, that
value is the scalar reward; otherwise the reward is the mean per-step reward.
Smoke mode and Colab / ``scripts/generate_grpo_evidence.py`` use similar
multi-step loops for metrics.

Examples:
  python train_praxis_grpo.py --smoke --steps 5 --tasks single-service-alert
  python train_praxis_grpo.py --steps 200 --learning-rate 1e-4 --tasks cascading-platform-failure,single-service-alert --model qwen-7b
  python train_praxis_grpo.py --smoke --no-wandb
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import csv
import json
import os
import random
import subprocess
import sys
import time
from collections.abc import Coroutine
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from praxis_env import PraxisAction, PraxisEnv
from praxis_env.server_bootstrap import (
    close_server_process_stderr,
    ensure_local_uvicorn,
)
from server.command_parser import is_known_action, parse_command

_T = TypeVar("_T")


MODEL_MAP = {
    "qwen-7b": "Qwen/Qwen2.5-7B-Instruct",
    "qwen-3b": "Qwen/Qwen2.5-3B-Instruct",
}

DEFAULT_TASKS = ("cascading-platform-failure", "single-service-alert")
CHECKPOINT_DIR = Path("checkpoints/praxis-grpo")

FALLBACK_COMMANDS = {
    "single-service-alert": [
        "query_logs service=auth timerange=5m",
        "check_config service=auth",
        "diagnose root_cause=bad_config",
        "rollback_deploy service=auth",
    ],
    "cascading-platform-failure": [
        "check_metrics service=database metric=connections",
        "check_metrics service=cdn metric=tls_handshake_failures",
        "check_metrics service=worker metric=memory",
        "check_config service=database",
        "check_config service=cdn",
        "check_config service=worker",
        "diagnose root_cause=db_pool_corrupted",
        "diagnose root_cause=cdn_tls_expired",
        "diagnose root_cause=worker_memory_leak",
        "rollback_deploy service=cdn",
        "scale_resource service=database resource=connection_pool",
        "rollback_deploy service=worker",
        (
            "submit_report root_causes=db_pool_corrupted,cdn_tls_expired,"
            "worker_memory_leak resolution=full_remediation_applied"
        ),
    ],
}


@dataclass
class StepTelemetry:
    reward: float
    planning: float
    memory: float
    recovery: float
    terminal: float
    loss: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train Praxis with GRPO/mtGRPO.")
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--tasks",
        default=",".join(DEFAULT_TASKS),
        help="Comma-separated task names.",
    )
    parser.add_argument(
        "--num-generations",
        "--group-size",
        dest="num_generations",
        type=int,
        default=8,
        help="GRPO num_generations / group size (TRL GRPOConfig.num_generations). Default 8.",
    )
    parser.add_argument("--max-turns", type=int, default=150)
    parser.add_argument(
        "--model",
        choices=tuple(MODEL_MAP.keys()),
        default="qwen-7b",
    )
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument(
        "--smoke-episodes",
        type=int,
        default=1,
        help="Smoke mode: run this many back-to-back episodes per task, concatenated into metrics.",
    )
    parser.add_argument(
        "--dataset-repeats",
        type=int,
        default=8,
        help="How many prompt repeats per task for GRPO train dataset.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("PRAXIS_URL", "http://127.0.0.1:7860"),
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=1e-4,
        help="TRL GRPOConfig learning rate (default 1e-4; production merge default).",
    )
    parser.add_argument(
        "--no-wandb",
        action="store_true",
        help="Do not init WandB/Trackio (for offline or CI).",
    )
    return parser.parse_args()


def parse_tasks(raw: str) -> list[str]:
    tasks = [part.strip() for part in raw.split(",") if part.strip()]
    return tasks or list(DEFAULT_TASKS)


def _run_async_blocking(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run *coro* to completion; safe if a caller (e.g. TRL) already has a running loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    def _runner() -> _T:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result()


def _extract_turn_credit(info: dict[str, Any]) -> tuple[float, float, float, float]:
    breakdown = info.get("breakdown", {}) if isinstance(info, dict) else {}
    if not isinstance(breakdown, dict):
        return (0.0, 0.0, 0.0, 0.0)
    return (
        float(breakdown.get("planning", 0.0)),
        float(breakdown.get("memory", 0.0)),
        float(breakdown.get("recovery", 0.0)),
        float(breakdown.get("terminal", 0.0)),
    )


def _fallback_command(task_name: str, step: int, rng: random.Random) -> str:
    commands = FALLBACK_COMMANDS.get(task_name) or [
        "escalate reason=no_commands_configured"
    ]
    if step <= len(commands):
        return commands[step - 1]
    return rng.choice(commands)


async def _run_smoke_episode(
    *,
    base_url: str,
    task_name: str,
    seed: int,
    max_steps: int,
) -> list[StepTelemetry]:
    rng = random.Random(f"{seed}:{task_name}")
    env = await PraxisEnv.from_url(base_url)
    metrics: list[StepTelemetry] = []
    try:
        await env.reset(task_name=task_name)
        for step in range(1, max_steps + 1):
            command = _fallback_command(task_name, step, rng)
            parsed = parse_command(command)
            if not is_known_action(parsed.action_type):
                command = "escalate reason=invalid_fallback_command"
            result = await env.step(PraxisAction(command=command))
            planning, memory, recovery, terminal = _extract_turn_credit(result.info)
            # GRPO objective is not available in smoke mode; mirror "loss" as
            # inverse reward so dashboards have a stable series.
            loss = max(0.0, 1.0 - float(result.reward))
            metrics.append(
                StepTelemetry(
                    reward=float(result.reward),
                    planning=planning,
                    memory=memory,
                    recovery=recovery,
                    terminal=terminal,
                    loss=loss,
                )
            )
            if result.done:
                break
    finally:
        await env.close()
    return metrics


def _init_wandb(run_name: str, enabled: bool) -> Any | None:
    if not enabled:
        return None
    try:
        import wandb  # type: ignore
    except Exception:
        return None
    mode = "online"
    run = wandb.init(project="praxis-mission-ops", name=run_name, mode=mode)
    return run


def _set_wandb_public(run: Any | None) -> str | None:
    if run is None:
        return None
    try:
        import wandb  # type: ignore

        api = wandb.Api()
        api_run = api.run(f"{run.entity}/{run.project}/{run.id}")
        api_run.read_only = False
        api_run.update()
        return api_run.url
    except Exception:
        return getattr(run, "url", None)


def _init_trackio(enabled: bool) -> Any | None:
    """Initialize Trackio. Set ``TRACKIO_SPACE_ID`` (e.g. ``user/trackio``) to
    sync metrics to a Hugging Face Space dashboard; absent the env var the run
    is local-only.
    """
    if not enabled:
        return None
    try:
        import trackio  # type: ignore
    except Exception:
        return None
    space_id = os.getenv("TRACKIO_SPACE_ID", "").strip() or None
    init_kwargs: dict[str, Any] = {"project": "praxis-mission-ops"}
    if space_id:
        init_kwargs["space_id"] = space_id
    try:
        trackio.init(**init_kwargs)
    except Exception:
        return None
    if space_id:
        print(f"[TRAIN] trackio_url=https://huggingface.co/spaces/{space_id}")
    else:
        print("[TRAIN] trackio: local-only (set TRACKIO_SPACE_ID to sync to a Space)")
    return trackio


def _log_step(
    trackio_mod: Any | None, wandb_run: Any | None, step: int, t: StepTelemetry
) -> None:
    payload = {
        "step": step,
        "mean_reward": t.reward,
        "planning": t.planning,
        "memory": t.memory,
        "recovery": t.recovery,
        "terminal": t.terminal,
        "loss": t.loss,
    }
    if wandb_run is not None:
        try:
            wandb_run.log(payload)
        except Exception:
            pass
    if trackio_mod is not None:
        try:
            trackio_mod.log(payload)
        except Exception:
            pass


def _save_checkpoint_manifest(
    *,
    args: argparse.Namespace,
    run_name: str,
    wandb_url: str | None,
    task_metrics: dict[str, list[StepTelemetry]],
    extra: dict[str, Any] | None = None,
    trackio_url: str | None = None,
    hub_model_id: str | None = None,
) -> Path:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "run_name": run_name,
        "model": MODEL_MAP[args.model],
        "learning_rate": float(getattr(args, "learning_rate", 1e-4)),
        "steps": args.steps,
        "smoke_episodes": int(getattr(args, "smoke_episodes", 1) or 1),
        "tasks": parse_tasks(args.tasks),
        "num_generations": args.num_generations,
        "max_turns": args.max_turns,
        "seed": args.seed,
        "smoke": bool(args.smoke),
        "wandb_url": wandb_url,
        "trackio_url": trackio_url,
        "hub_model_id": hub_model_id or None,
        "summary": {
            task: {
                "steps_observed": len(metrics),
                "mean_reward": (
                    sum(t.reward for t in metrics) / len(metrics) if metrics else 0.0
                ),
            }
            for task, metrics in task_metrics.items()
        },
    }
    if extra:
        manifest["extra"] = extra
    manifest_path = CHECKPOINT_DIR / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def _save_metrics_csv(task_metrics: dict[str, list[StepTelemetry]]) -> Path:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = CHECKPOINT_DIR / "metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "task",
                "step",
                "reward",
                "planning",
                "memory",
                "recovery",
                "terminal",
                "loss",
            ]
        )
        for task_name, metrics in task_metrics.items():
            for step, t in enumerate(metrics, start=1):
                writer.writerow(
                    [
                        task_name,
                        step,
                        f"{t.reward:.6f}",
                        f"{t.planning:.6f}",
                        f"{t.memory:.6f}",
                        f"{t.recovery:.6f}",
                        f"{t.terminal:.6f}",
                        f"{t.loss:.6f}",
                    ]
                )
    return csv_path


def run_smoke(args: argparse.Namespace) -> int:
    if int(args.smoke_episodes) < 1:
        print("[SMOKE] --smoke-episodes must be >= 1", flush=True)
        return 2
    run_name = f"praxis-smoke-{datetime.now(tz=timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    _log_remote = not bool(getattr(args, "no_wandb", False))
    wandb_run = _init_wandb(run_name, enabled=_log_remote)
    trackio_mod = _init_trackio(enabled=_log_remote)

    server_proc, _log_path = ensure_local_uvicorn(
        args.base_url,
        start_message="[SMOKE] Starting local environment server...",
        healthy_message="[SMOKE] Server is healthy.",
    )
    try:
        task_metrics: dict[str, list[StepTelemetry]] = {}
        for idx, task_name in enumerate(parse_tasks(args.tasks)):
            metrics: list[StepTelemetry] = []
            for ep in range(int(args.smoke_episodes)):
                chunk = asyncio.run(
                    _run_smoke_episode(
                        base_url=args.base_url,
                        task_name=task_name,
                        seed=args.seed + idx * 10_000 + ep,
                        max_steps=args.steps,
                    )
                )
                metrics.extend(chunk)
            task_metrics[task_name] = metrics
            global_step = 0
            for telemetry in metrics:
                global_step += 1
                _log_step(trackio_mod, wandb_run, global_step, telemetry)
            mean_reward = (
                sum(t.reward for t in metrics) / len(metrics) if metrics else 0.0
            )
            print(
                f"[SMOKE] task={task_name} episodes={int(args.smoke_episodes)} "
                f"steps={len(metrics)} mean_reward={mean_reward:.4f}"
            )

        wandb_url = _set_wandb_public(wandb_run)
        if wandb_run is not None:
            try:
                wandb_run.finish()
            except Exception:
                pass
        trackio_space = os.getenv("TRACKIO_SPACE_ID", "").strip()
        trackio_url = (
            f"https://huggingface.co/spaces/{trackio_space}"
            if trackio_space and trackio_mod is not None
            else None
        )
        manifest = _save_checkpoint_manifest(
            args=args,
            run_name=run_name,
            wandb_url=wandb_url,
            task_metrics=task_metrics,
            trackio_url=trackio_url,
        )
        metrics_csv = _save_metrics_csv(task_metrics)
        print(f"[SMOKE] checkpoint_manifest={manifest.as_posix()}")
        print(f"[SMOKE] metrics_csv={metrics_csv.as_posix()}")
        if trackio_url:
            print(f"[SMOKE] trackio_url={trackio_url}")
        return 0
    finally:
        if server_proc is not None:
            server_proc.terminate()
            server_proc.wait()
            close_server_process_stderr(server_proc)


def _normalize_completion(completion: Any) -> str:
    if isinstance(completion, str):
        return completion.strip()
    if isinstance(completion, list):
        chunks: list[str] = []
        for item in completion:
            if isinstance(item, dict):
                text = item.get("content") or item.get("text") or ""
                if text:
                    chunks.append(str(text))
            elif isinstance(item, str):
                chunks.append(item)
        return " ".join(chunks).strip()
    if isinstance(completion, dict):
        return str(completion.get("content") or completion.get("text") or "").strip()
    return str(completion).strip()


def _pick_command_from_completion(text: str, task_name: str, seed: int) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        rng = random.Random(f"{seed}:{task_name}:empty")
        return _fallback_command(task_name, 1, rng)
    command = lines[0]
    parsed = parse_command(command)
    if is_known_action(parsed.action_type):
        return command
    rng = random.Random(f"{seed}:{task_name}:{text[:32]}")
    return _fallback_command(task_name, 1, rng)


def _commands_for_rollout(completion_text: str, task_name: str, seed: int) -> list[str]:
    """
    One command per non-empty line. Unknown lines are replaced with a
    deterministic fallback for that step (same family as ``_run_smoke_episode``).
    If there are no lines, one fallback is produced from the first line heuristic.
    """
    lines = [ln.strip() for ln in (completion_text or "").splitlines() if ln.strip()]
    if not lines:
        return [_pick_command_from_completion(completion_text or "", task_name, seed)]
    out: list[str] = []
    rng = random.Random(f"{seed}:{task_name}")
    for step_idx, line in enumerate(lines, start=1):
        parsed = parse_command(line)
        if is_known_action(parsed.action_type):
            out.append(line)
        else:
            out.append(_fallback_command(task_name, step_idx, rng))
    return out


async def _rollout_episode_return_score(
    *,
    base_url: str,
    task_name: str,
    seed: int,
    completion_text: str,
    max_steps: int,
) -> float:
    """
    Full trajectory reward for GRPO: execute each parsed command in one session
    (after a single ``reset``), at most ``max_steps`` environment steps. Prefer
    ``/state`` ``final_score`` when the server marks the episode terminal.
    """
    env = await PraxisEnv.from_url(base_url)
    try:
        await env.reset(task_name=task_name)
        commands = _commands_for_rollout(completion_text, task_name, seed)
        step_rewards: list[float] = []
        for i, command in enumerate(commands):
            if i >= max_steps:
                break
            result = await env.step(PraxisAction(command=command))
            step_rewards.append(float(result.reward))
            if result.done:
                state = await env.get_state()
                if state.final_score is not None:
                    return float(state.final_score)
                break
        if not step_rewards:
            return 0.01
        state = await env.get_state()
        if state.final_score is not None:
            return float(state.final_score)
        return float(sum(step_rewards) / len(step_rewards))
    finally:
        await env.close()


def _build_training_rows(tasks: list[str], repeats: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for task_name in tasks:
        for _ in range(max(1, repeats)):
            rows.append(
                {
                    "prompt": (
                        "You are an SRE incident commander. "
                        f"Investigate and resolve task: {task_name}. "
                        "Reply with one valid Praxis command per line; use multiple "
                        "lines for a full remediation sequence when needed."
                    ),
                    "task_name": task_name,
                }
            )
    return rows


def _extract_history_series(log_history: list[dict[str, Any]]) -> list[StepTelemetry]:
    metrics: list[StepTelemetry] = []
    running_reward = 0.0
    for item in log_history:
        if "reward" in item:
            try:
                running_reward = float(item.get("reward", running_reward))
            except Exception:
                pass
        if "loss" not in item:
            continue
        try:
            loss = float(item["loss"])
        except Exception:
            continue
        metrics.append(
            StepTelemetry(
                reward=running_reward,
                planning=0.0,
                memory=0.0,
                recovery=0.0,
                terminal=0.0,
                loss=loss,
            )
        )
    return metrics


def run_training(args: argparse.Namespace) -> int:
    model_name = MODEL_MAP[args.model]
    run_name = f"praxis-grpo-{args.model}-{datetime.now(tz=timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    try:
        import torch  # type: ignore
        from datasets import Dataset  # type: ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
        from trl import GRPOConfig, GRPOTrainer  # type: ignore
    except Exception as exc:
        print(f"[ERROR] Missing training dependencies: {exc}")
        return 2

    use_unsloth = False
    fast_model = None
    try:
        from unsloth import FastLanguageModel  # type: ignore

        fast_model = FastLanguageModel
        use_unsloth = True
    except Exception:
        use_unsloth = False

    _log_remote = not bool(getattr(args, "no_wandb", False))
    wandb_run = _init_wandb(run_name, enabled=_log_remote)
    trackio_mod = _init_trackio(enabled=_log_remote)
    server_proc: subprocess.Popen[Any] | None = None

    lr = float(getattr(args, "learning_rate", 1e-4))
    print(f"[TRAIN] model={model_name} unsloth={use_unsloth} learning_rate={lr}")
    start = time.perf_counter()
    try:
        server_proc, _ = ensure_local_uvicorn(
            args.base_url,
            start_message="[TRAIN] Starting local environment server...",
            healthy_message="[TRAIN] Server is healthy.",
        )
        if use_unsloth and fast_model is not None:
            model, tokenizer = fast_model.from_pretrained(
                model_name=model_name,
                max_seq_length=4096,
                load_in_4bit=True,
            )
        else:
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForCausalLM.from_pretrained(model_name)

        task_list = parse_tasks(args.tasks)
        rows = _build_training_rows(task_list, repeats=args.dataset_repeats)
        train_dataset = Dataset.from_list(rows)
        if tokenizer.pad_token is None and tokenizer.eos_token is not None:
            tokenizer.pad_token = tokenizer.eos_token

        seed = int(args.seed)
        random.seed(seed)
        try:
            torch.manual_seed(seed)
        except Exception:
            pass

        max_turns = int(args.max_turns)

        def reward_func(
            prompts: list[Any], completions: list[Any], **_: Any
        ) -> list[float]:
            rewards: list[float] = []
            for idx, completion in enumerate(completions):
                completion_text = _normalize_completion(completion)
                prompt_obj = prompts[idx] if idx < len(prompts) else {}
                task_name = "single-service-alert"
                if isinstance(prompt_obj, dict):
                    task_name = str(prompt_obj.get("task_name") or task_name)
                score = _run_async_blocking(
                    _rollout_episode_return_score(
                        base_url=args.base_url,
                        task_name=task_name,
                        seed=seed + idx,
                        completion_text=completion_text,
                        max_steps=max_turns,
                    )
                )
                rewards.append(score)
            return rewards

        hub_model_id = os.getenv("HF_HUB_MODEL_ID", "").strip()
        grpo_config_kwargs: dict[str, Any] = dict(
            output_dir=str(CHECKPOINT_DIR),
            learning_rate=lr,
            num_generations=int(args.num_generations),
            per_device_train_batch_size=1,
            gradient_accumulation_steps=1,
            num_train_epochs=1,
            max_steps=int(args.steps),
            max_prompt_length=512,
            max_completion_length=256,
            logging_steps=1,
            save_steps=max(1, int(args.steps) // 2),
            report_to=["trackio"] if trackio_mod is not None else [],
            seed=seed,
        )
        # Hub push is gated on ``HF_HUB_MODEL_ID`` so local runs stay offline;
        # HF Jobs invocations supply the env var so the trained checkpoint
        # persists past the ephemeral container.
        if hub_model_id:
            grpo_config_kwargs.update(
                push_to_hub=True,
                hub_model_id=hub_model_id,
                hub_strategy="every_save",
            )
            print(f"[TRAIN] hub_model_id={hub_model_id} push_to_hub=True")
        grpo_config = GRPOConfig(**grpo_config_kwargs)

        trainer_kwargs = {
            "model": model,
            "args": grpo_config,
            "train_dataset": train_dataset,
            "reward_funcs": [reward_func],
        }
        trainer = None
        try:
            trainer = GRPOTrainer(**trainer_kwargs, tokenizer=tokenizer)
        except TypeError:
            trainer = GRPOTrainer(**trainer_kwargs, processing_class=tokenizer)

        train_result = trainer.train()
        _ = train_result
        log_history = list(getattr(trainer.state, "log_history", []) or [])
        training_metrics = _extract_history_series(log_history)
        if not training_metrics:
            training_metrics = [
                StepTelemetry(
                    reward=0.0,
                    planning=0.0,
                    memory=0.0,
                    recovery=0.0,
                    terminal=0.0,
                    loss=0.0,
                )
            ]

        for step, telemetry in enumerate(training_metrics, start=1):
            _log_step(trackio_mod, wandb_run, step, telemetry)

        split = max(1, len(training_metrics) // 3)
        baseline_slice = training_metrics[:split]
        trained_slice = training_metrics[-split:]
        baseline_mean = sum(t.reward for t in baseline_slice) / len(baseline_slice)
        trained_mean = sum(t.reward for t in trained_slice) / len(trained_slice)

        task_metrics: dict[str, list[StepTelemetry]] = {
            "training-loop": training_metrics,
        }

        elapsed = round(time.perf_counter() - start, 3)
        extra = {
            "mode": "grpo",
            "dataset_rows": len(rows),
            "training_steps_logged": len(training_metrics),
            "baseline_mean_reward": baseline_mean,
            "trained_mean_reward": trained_mean,
            "reward_lift": (trained_mean / baseline_mean)
            if baseline_mean > 0
            else None,
            "runtime_seconds": elapsed,
        }

        wandb_url = _set_wandb_public(wandb_run)
        trackio_space = os.getenv("TRACKIO_SPACE_ID", "").strip()
        trackio_url = (
            f"https://huggingface.co/spaces/{trackio_space}"
            if trackio_space and trackio_mod is not None
            else None
        )
        manifest = _save_checkpoint_manifest(
            args=args,
            run_name=run_name,
            wandb_url=wandb_url,
            task_metrics=task_metrics,
            extra=extra,
            trackio_url=trackio_url,
            hub_model_id=hub_model_id or None,
        )
        metrics_csv = _save_metrics_csv(task_metrics)
        print(f"[TRAIN] checkpoint_manifest={manifest.as_posix()}")
        print(f"[TRAIN] metrics_csv={metrics_csv.as_posix()}")
        print(f"[TRAIN] baseline_mean_reward={baseline_mean:.6f}")
        print(f"[TRAIN] trained_mean_reward={trained_mean:.6f}")
        if extra.get("reward_lift") is not None:
            print(f"[TRAIN] reward_lift={float(extra['reward_lift']):.4f}x")
        if trackio_url:
            print(f"[TRAIN] trackio_url={trackio_url}")
        if hub_model_id:
            print(f"[TRAIN] hub_repo=https://huggingface.co/{hub_model_id}")
        return 0
    finally:
        if wandb_run is not None:
            try:
                wandb_run.finish()
            except Exception:
                pass
        if server_proc is not None:
            server_proc.terminate()
            server_proc.wait()
            close_server_process_stderr(server_proc)


def main() -> int:
    args = parse_args()
    if args.smoke:
        return run_smoke(args)
    return run_training(args)


if __name__ == "__main__":
    sys.exit(main())
