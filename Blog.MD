# We built a training environment for SRE agents. Here is what happened.

Production incidents are not questions. They are threads. You pull one end, something else unravels, you rule out three hypotheses, you circle back, and somewhere in there you either find the problem or you time out and escalate.

We wanted to know if you could train a language model to follow that thread. Not just a plausible-sounding answer, but a real diagnostic that converges on the right fix. So we built Praxis: a stateful FastAPI environment that puts a model on-call, scores its reasoning, and lets you train on the difference between a model that gets lucky and one that does the work.

This is what we built, what broke, and what the training curves showed.

## The core loop

Three endpoints. That is the contract.

`POST /reset` starts an incident. The server loads a scenario and returns a session id when the API needs it. `POST /step` takes one SRE command, runs it against live world state, and returns an observation plus a scored reward in `info`. `GET /state` is episode metadata when you want stats without the full log.

The reward breakdown is what you train on. We split it into four named parts in `info.breakdown`: planning, memory, recovery, and terminal credit. The point is to see *why* a run scored, not just a scalar at the end. A policy that walks for twelve steps and stumbles on the fix is not the same as one that runs four targeted steps and ends in the same place. Scoring is wired in [server/reward.py](https://github.com/GunaPalanivel/Praxis/blob/main/server/reward.py).

## What we built, and in what order

**First: a way to prove it worked.** Before the training story mattered, we built smoke paths and evidence scripts. When we said the environment runs, we wanted console output and committed artifacts, not a one-off demo. That paid off when Colab config drifted. One broken baseline is fixable. Two at once is a day lost.

**Rate limits came fast.** Stacking many `/step` calls during smoke started returning HTTP 429. The server reads `PRAXIS_RATE_LIMIT_STEP` and `PRAXIS_RATE_LIMIT_RESET` (see [server/app.py](https://github.com/GunaPalanivel/Praxis/blob/main/server/app.py)). We also added `--smoke-episodes` in [train_praxis_grpo.py](https://github.com/GunaPalanivel/Praxis/blob/main/train_praxis_grpo.py) so you can string episodes and fill `metrics.csv` without inventing data. Rerun notes live in [docs/training_links.md](https://github.com/GunaPalanivel/Praxis/blob/main/docs/training_links.md).

**How we start the process matters.** The Docker [Dockerfile](https://github.com/GunaPalanivel/Praxis/blob/main/Dockerfile) uses `uvicorn server.app:app` in `CMD` as the single ASGI entry. A class of failure shows up if you start with a `python -m` path that re-imports the app and spins uvicorn in-process: you can get two imports and two session managers, and the training client talks to a different world than the routes. We standardize on one process, one import graph.

**TRL in Colab is not a local script.** Init order in a cell is unforgiving. We fixed the GRPO config flow in the notebook so a cold Colab run does not die on the first `train()`. Boring work. High save rate.

**Short CSVs lie with flat curves.** A real improvement can look flat if you only log a dozen points. We extended the logged series so the slope is visible. The direction matters more than a hero number.

## The training results, shown honestly

The rollout comparison is the clearest story we can show. Put baseline and trained on the same axes, then read the command sequence in the text logs if you want the play-by-play.

Early runs look like triage with weak coupling between steps. Later runs look like someone who narrows the space on purpose. Not magic. Consistent with longer metrics once you have enough rows.

The reward curve goes up. The loss series moves down on our smoke-style proxy. Neither line is a Hollywood launch. It is real env stepping, not a replay file.

Evidence files are pinned to the `feat/grpo-colab-evidence` branch in GitHub so a judge can line this Space up with a PR.

- Rollout: `https://raw.githubusercontent.com/GunaPalanivel/Praxis/feat/grpo-colab-evidence/docs/rollout_compare.png`
- Reward and loss: `https://raw.githubusercontent.com/GunaPalanivel/Praxis/feat/grpo-colab-evidence/reward_curve.png` and `https://raw.githubusercontent.com/GunaPalanivel/Praxis/feat/grpo-colab-evidence/loss_curve.png`
- Writeup: [docs/training_evolution.md](https://github.com/GunaPalanivel/Praxis/blob/feat/grpo-colab-evidence/docs/training_evolution.md)

![Rollout compare](https://raw.githubusercontent.com/GunaPalanivel/Praxis/feat/grpo-colab-evidence/docs/rollout_compare.png)

![Reward curve](https://raw.githubusercontent.com/GunaPalanivel/Praxis/feat/grpo-colab-evidence/reward_curve.png)

![Loss curve](https://raw.githubusercontent.com/GunaPalanivel/Praxis/feat/grpo-colab-evidence/loss_curve.png)

If the README and the chart disagree, that is a bug. Tell us.

## How the team divided the work

Each person owned a lane. Reviews were for catching mistakes, not for optics.

**Gokul** ([@Gokul287](https://github.com/Gokul287)) carried a large environment integration, then a fast follow pass for review items. Big merge plus quick cleanup beats one perfect shot that never lands.

**Sneha** ([@snehasneha56526-arch](https://github.com/snehasneha56526-arch)) tied evidence to claims. A demo without a path to reproduce is a liability when someone actually reads the repo.

**Guna** ([@GunaPalanivel](https://github.com/GunaPalanivel)) ran coordination: tracker, deployment smoke, README. The job is to make what judges see match what you can run again.

[Issue 44](https://github.com/GunaPalanivel/Praxis/issues/44) is still open: a before and after motion asset for the rollout story. It is open because we want it done right, not just ticked.

## What is still broken or unknown

**Success and wandering.** [inference.py](https://github.com/GunaPalanivel/Praxis/blob/main/inference.py) uses `SUCCESS_SCORE_THRESHOLD` (default `0.50`) to mark a run as successful at the end. The rubric still has small per-step investigation credits. A bad policy can look busy even when it never earns a high task score. Raising the bar or tightening outcome gates is still fair game.

**Repo-shaped memorization.** Fixed scenarios in the open repo can be memorized. `POST /reset` accepts `seed` for **procedural-incident** and **cascading-platform-failure**; other tasks ignore seed today (see [server/praxis_environment.py](https://github.com/GunaPalanivel/Praxis/blob/main/server/praxis_environment.py)). Broader use of `seed` across all tasks, or more procedural surface, is the next infrastructure step if you want anti-memorization to be a first-class story.

**Memory cutoff vs episode length.** The memory module uses a context cutoff (default 30) with scenario overrides. Short tasks (for example 15 max steps) can finish before the cutoff changes what the agent sees. The mission task runs up to 150 steps with cutoff 30, so the memory path is not theoretical there.

## Where everything lives

- Live environment: [gp5901-praxis.hf.space](https://gp5901-praxis.hf.space)
- HF Space: [huggingface.co/spaces/gp5901/praxis](https://huggingface.co/spaces/gp5901/praxis)
- Source: [github.com/GunaPalanivel/Praxis](https://github.com/GunaPalanivel/Praxis)
- Colab: [open the notebook in Colab](https://colab.research.google.com/github/GunaPalanivel/Praxis/blob/main/praxis_grpo_colab.ipynb)
- Rollout image in repo: `docs/rollout_compare.png`
- Training evolution: `docs/training_evolution.md`
