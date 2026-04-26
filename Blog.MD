# Praxis: training an agent on real incident workflows

## What we built

Praxis is a FastAPI environment that looks like a live incident bridge. The agent types SRE style commands, reads logs and metrics, and gets graded on how it triages, diagnoses, and remediates. This Space hosts the public HTTP API so training and demos can use the same contract as a research notebook.

## Why this is hard for LLMs

This is not a one shot QA task. The agent must work across many steps, keep track of an investigation thread, and avoid shortcuts that only look good on a single turn. The reward is not a single “final answer” button. The model has to follow a process that still works when the incident gets messy.

## How the environment works

You call `POST /reset` to start a task. The response includes a session id when the server needs it. You call `POST /step` with one command per step. The response returns an observation, a reward, a done flag, and extra info. `GET /state` is a small summary if you need episode metadata without a full observation.

## Reward design in plain terms

The server uses composable rubrics. The names in the `info.breakdown` field line up with planning, memory, recovery, and terminal credit. The idea is to reward the parts of the job that still matter in production, not just a lucky last step.

## How we trained

We ship a Colab first workflow in the GitHub repo. The notebook is named `praxis_grpo_colab.ipynb`. The notebook is wired to this Space base URL for live rollouts, so the trainer is not learning from a frozen replay that never changes.

We also run a local smoke loop in `train_praxis_grpo.py` to emit `checkpoints/praxis-grpo/metrics.csv` and to regenerate plots when you need fresh curves without a full GPU run.

## Results and plots

These files are pinned to the `feat/grpo-colab-evidence` branch in GitHub so a judge can line up the Space story with a PR or branch review.

- Rollout before and after: `https://raw.githubusercontent.com/GunaPalanivel/Praxis/feat/grpo-colab-evidence/docs/rollout_compare.png`
- Training reward and loss: `https://raw.githubusercontent.com/GunaPalanivel/Praxis/feat/grpo-colab-evidence/reward_curve.png` and `https://raw.githubusercontent.com/GunaPalanivel/Praxis/feat/grpo-colab-evidence/loss_curve.png`
- Longer writeup in the repo: `https://github.com/GunaPalanivel/Praxis/blob/feat/grpo-colab-evidence/docs/training_evolution.md`

![Rollout compare](https://raw.githubusercontent.com/GunaPalanivel/Praxis/feat/grpo-colab-evidence/docs/rollout_compare.png)

![Reward curve](https://raw.githubusercontent.com/GunaPalanivel/Praxis/feat/grpo-colab-evidence/reward_curve.png)

![Loss curve](https://raw.githubusercontent.com/GunaPalanivel/Praxis/feat/grpo-colab-evidence/loss_curve.png)

## How we built it, told as a build log

**Contributors (from git history):** the most active commit authors are Guna Palanivel, Gokul G, Sneha, and a small set of co authors on focused fixes.

1. `d48975d` added real world smoke and evidence scripts. This is the spine that turns “it runs on my machine” into repeatable console checks.
2. `99f748c` vendored the artifact dataset and third party license notice. This keeps provenance clean when we show real log snippets to judges.
3. `2ff14ce` added the GRPO training entry point with a smoke path. This is the on ramp for a Colab or GPU run without a mystery wrapper.
4. `87bc978` committed reward and loss images plus a link bundle. This is the “show your work” moment for the training story.
5. `2ef6142` added the Colab notebook and the first training curves, so the training story is a file you can point to, not a screenshot in chat.
6. `6855e98` fixed Colab init details for the TRL GRPO config, which reduces “works in README but fails in a cell” risk.
7. `9ee39b4` added rollout comparison and evolution logs, so the lift story is paired with a chart and a short narrative.

**Merged PRs that moved the project:**

- **PR 51 and PR 52 (Gokul287):** shipped a large P0 bundle and then fixed review follow ups. This reduced integration risk by landing the environment and follow up fixes in two controlled waves.
- **PR 53 (snehasneha56526 arch):** shipped an evidence bundle that ties environment work to the submission artifacts. This helped keep “what we show” aligned with what we can reproduce.

**Open tracking work (GitHub, as of 2026 04 26):**

- **Issue 50 (GunaPalanivel):** submission tracker, still the umbrella until every judge facing box is done.
- **Issue 48 (GunaPalanivel):** deployment and smoke pack, still open while we keep Space and CI green together.
- **Issue 44 (Gokul287):** demo asset and trophy rollout story, still open if we add a short GIF or a tighter before and after.
- **Issue 49 (GunaPalanivel):** README and storytelling polish, still open while we keep tightening the first screen for judges.

**Blockers we hit, and what we did next:**

- **Local rate limits on `/step`:** when we stacked many quick steps, the dev server returned HTTP 429. We raised the local limit with `PRAXIS_RATE_LIMIT_STEP` and `PRAXIS_RATE_LIMIT_RESET` for the smoke run, and we also added a `--smoke-episodes` option so we can log long series without faking data.
- **TRL stack not installed on a bare machine:** the repo documents the path, and the Colab file is the primary GPU story. The smoke path still gives honest curves by stepping the live env.
- **Lift claims vs a short log:** a short CSV makes charts look flat even when the system works. The longer series is there to show trend lines with enough points to read.

## Links

- Live Space app: `https://gp5901-praxis.hf.space`
- Space project page: `https://huggingface.co/spaces/gp5901/praxis`
- GitHub source: `https://github.com/GunaPalanivel/Praxis`
- Open in Colab: `https://colab.research.google.com/github/GunaPalanivel/Praxis/blob/main/praxis_grpo_colab.ipynb`
