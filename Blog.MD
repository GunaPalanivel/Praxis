# We Built a Training Environment for SRE Agents. Here Is What Happened.

Production incidents are not questions. They are threads. You pull one end, something else unravels, you rule out three hypotheses, you circle back, and somewhere in there you either find the problem or you time out and escalate.

We wanted to know if you could train a language model to follow that thread — not produce a plausible-sounding answer, but run a real diagnostic that converges on the right fix before the SLO window closes. The cost of getting it wrong is a bad rollback or a 3am escalation that did not need to happen.

So we built Praxis: a stateful FastAPI environment that puts a model on-call, scores its reasoning, and lets you train on the difference between a model that gets lucky and one that does the work.

This is what we built, what broke, and what the training curves showed.

---

## The Core Loop

Three endpoints. That is the contract.

`POST /reset` starts an incident. The server loads a scenario and returns a session id. `POST /step` takes one SRE command, runs it against live world state, and returns an observation plus a scored reward in `info`. `GET /state` returns episode metadata when you want stats without the full log.

The reward breakdown is what you train on. We split it into four named parts in `info.breakdown`: planning, memory, recovery, and terminal credit. The point is to see _why_ a run scored, not just a scalar at the end. A policy that walks for twelve steps and stumbles on the fix is not the same as one that runs four targeted steps and ends in the same place.

For example: a policy that starts with `check_metrics` before `check_logs` on a memory-leak scenario scores higher on planning than one that reaches the same finding in reverse order. Same terminal outcome, different reasoning path, different reward. Scoring is wired in [server/reward.py](https://github.com/GunaPalanivel/Praxis/blob/main/server/reward.py).

---

## What We Built, and in What Order

**First: a way to prove it worked.** Before the training story mattered, we built smoke paths and evidence scripts. When we said the environment runs, we wanted console output and committed artifacts, not a one-off demo. That paid off when Colab config drifted. One broken baseline is fixable. Two at once is a day lost.

**Rate limits came fast.** Stacking many `/step` calls during smoke runs started returning HTTP 429. The server now reads `PRAXIS_RATE_LIMIT_STEP` and `PRAXIS_RATE_LIMIT_RESET` (see [server/app.py](https://github.com/GunaPalanivel/Praxis/blob/main/server/app.py)). We also added `--smoke-episodes` in [train_praxis_grpo.py](https://github.com/GunaPalanivel/Praxis/blob/main/train_praxis_grpo.py) so you can string episodes and fill `metrics.csv` without inventing data. Rerun notes live in [docs/training_links.md](https://github.com/GunaPalanivel/Praxis/blob/main/docs/training_links.md).

**The Dockerfile CMD was wrong in a specific way.** Running via `python -m server.app` re-imports the module and calls `create_app()` twice — one `SessionManager` from the module-scope import, one from the uvicorn inner spin. The training client and the routes end up talking to different state. We use `CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]` in the [Dockerfile](https://github.com/GunaPalanivel/Praxis/blob/main/Dockerfile) to guarantee one import graph, one session manager.

**TRL in Colab is not a local script.** Init order in a cell is unforgiving. We fixed the GRPO config flow in the notebook so a cold Colab run does not die on the first `train()`. Boring work. High save rate.

**Short CSVs lie with flat curves.** A real improvement can look flat if you only log a dozen points. We extended the logged series so the slope is visible. The direction matters more than a hero number.

---

## The Training Results, Shown Honestly

The command sequence tells the story better than the curve.

In the early run: `check_metrics` → `check_logs` → `check_metrics` again → timeout. No thread. Each step weakly coupled to the last. In the trained run: `check_metrics` → `isolate_service` → `check_dependency` → `rollback_deploy` → resolved. Four commands, directed reasoning, terminal credit earned. That is what the reward breakdown was designed to produce.

The reward curve goes up. The loss series comes down on our smoke-style proxy. Neither line is a Hollywood launch. It is real environment stepping, not a replay file.

Evidence files are pinned to the `feat/grpo-colab-evidence` branch so a judge can line this Space up with a specific PR. If the README and the chart disagree, that is a bug. Tell us.

Full training writeup: [docs/training_evolution.md](https://github.com/GunaPalanivel/Praxis/blob/feat/grpo-colab-evidence/docs/training_evolution.md)

---

## How the Team Divided the Work

Each person owned a lane. Reviews were for catching mistakes, not for optics.

**Gokul** ([@Gokul287](https://github.com/Gokul287)) carried the large environment integration, then a fast follow pass for review items. Big merge plus quick cleanup beats one perfect shot that never lands.

**Sneha** ([@snehasneha56526-arch](https://github.com/snehasneha56526-arch)) tied evidence to claims. A demo without a path to reproduce is a liability when someone actually reads the repo.

**Guna** ([@GunaPalanivel](https://github.com/GunaPalanivel)) ran coordination: tracker, deployment smoke, README. The job is to make what judges see match what you can run again.

[Issue 44](https://github.com/GunaPalanivel/Praxis/issues/44) is still open: a before-and-after motion asset for the rollout story. It is open because we want it done right, not just ticked.

---

## What Is Still Broken or Unknown

**The success threshold was too low and we fixed it.** The original `SUCCESS_SCORE_THRESHOLD` default was `0.10` — low enough that a policy could pass by taking any ten steps without meaningful investigation. We raised it to `0.50`, which requires at least partial planning and terminal credit to register as a success. Outcome gates — requiring `incident_resolved=True` before any run counts — are the next tightening pass. See [inference.py](https://github.com/GunaPalanivel/Praxis/blob/main/inference.py).

**Repo-shaped memorization is a real risk.** Fixed scenarios in an open repo can be memorized. `POST /reset` accepts `seed` for `procedural-incident` and `cascading-platform-failure`; other tasks ignore seed today (see [server/praxis_environment.py](https://github.com/GunaPalanivel/Praxis/blob/main/server/praxis_environment.py)). Broader seed coverage across all task types, or more procedural surface area, is the next infrastructure investment if anti-memorization is a first-class requirement.

**Memory cutoff is live on long tasks, dead on short ones.** The memory module uses a context cutoff at step 30. The mission task runs up to 150 steps with cutoff 30, so the save/recall path is exercised during real training, not just in unit tests. Shorter tasks — 15 max steps — exit before cutoff fires. The fix is either per-scenario cutoff tuning down to step 8–12, or extending short task horizons to 40+ steps. Both are valid.

---

## Where Everything Lives

- Live environment: [gp5901-praxis.hf.space](https://gp5901-praxis.hf.space)
- HF Space: [huggingface.co/spaces/gp5901/praxis](https://huggingface.co/spaces/gp5901/praxis)
- Source: [github.com/GunaPalanivel/Praxis](https://github.com/GunaPalanivel/Praxis)
- Colab notebook: [open directly in Colab](https://colab.research.google.com/github/GunaPalanivel/Praxis/blob/main/praxis_grpo_colab.ipynb)
- Rollout comparison: `docs/rollout_compare.png` on `feat/grpo-colab-evidence`
- Training evolution: `docs/training_evolution.md`
