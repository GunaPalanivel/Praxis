# Training Links

Run date: 2026-04-26

- **Public Space:** after server/API changes land on `main`, sync **https://huggingface.co/spaces/gp5901/praxis** so **https://gp5901-praxis.hf.space** matches the repo (see [deployment.md](deployment.md) § *Keep the public Space in sync*).
- **Colab judge evidence vs toy smoke:** The canonical notebook is [`praxis_grpo_colab.ipynb`](https://colab.research.google.com/github/GunaPalanivel/Praxis/blob/main/praxis_grpo_colab.ipynb) and runs **`uv run train_praxis_grpo.py`** with **`--learning-rate 1e-4`** and **`--group-size 8`**. For TRL+Unsloth plots on GPU, do **not** set `PRAXIS_COLAB_FORCE_SMOKE`. This repo does **not** use `PRAXIS_NOTEBOOK_SMOKE` or an in-notebook `TrainConfig` — if your shell still has `PRAXIS_NOTEBOOK_SMOKE`, remove it (`Remove-Item Env:PRAXIS_NOTEBOOK_SMOKE` on Windows). For a **long** judge run, set **`PRAXIS_COLAB_FULL=1`** before the train cell (200 steps, four tasks, same defaults as HF Jobs).
- Plotting / evidence scripts (`scripts/build_production_evidence.py`, `scripts/plot_curves.py`, `scripts/generate_grpo_evidence.py`) need the **`evidence`** optional extra. With uv: `uv sync --all-extras` (includes `evidence`) or `uv sync --extra evidence`.
- Logging: this branch is **Trackio-only** for production. Set `TRACKIO_SPACE_ID=<user>/<space>` in the environment (e.g. `gp5901/trackio`); the trainer reports to that Space and writes `trackio_url` to `checkpoints/praxis-grpo/run_manifest.json`. `_init_wandb` is a no-op stub (kept for back-compat with older docs); `--no-wandb` is still accepted as the offline/CI switch and now also disables Trackio.
- YouTube: record a 2–3 min Space screencast, publish unlisted or public, then paste the URL into the **Video** row of the [README § Links & materials](https://github.com/GunaPalanivel/Praxis/blob/main/README.md#links--materials-judges-start-here) table.
- Local run manifest: `checkpoints/praxis-grpo/run_manifest.json`
- Local metrics CSV: `checkpoints/praxis-grpo/metrics.csv`
- Rollout baseline log: `docs/rollout_baseline.txt`
- Rollout trained log: `docs/rollout_trained.txt`
- Rollout comparison plot: `docs/figures/rollout_compare.png`
- Evolution summary: `docs/training_evolution.md`
- Long smoke refresh on this date: 170 logged rows in `checkpoints/praxis-grpo/metrics.csv` (stacked episodes via `python train_praxis_grpo.py --smoke --smoke-episodes 10 --steps 30 ...`)

When credentials are available, re-run locally:

```bash
python train_praxis_grpo.py --steps 200 --learning-rate 1e-4 --tasks cascading-platform-failure,single-service-alert --model qwen-7b
```

## Production GRPO run on HF Jobs

The full GPU run referenced in the production-merge checklist (lr=1e-4,
group_size=8, 200+ episodes) is submitted via the bootstrap launcher, not
by hand. See `scripts/README.md` for the one-command flow. Quick reference:

```bash
git push origin HEAD                                  # trainer SHA must be on origin
python scripts/submit_hf_grpo_job.py \
  --hub-model-id gp5901/praxis-grpo-7b \
  --trackio-space-id gp5901/trackio \
  --flavor a10g-large \
  --timeout 5h
```

The submitter does a `git ls-remote` preflight to mitigate the HF Jobs
clone race (the GPU container's `git clone` would otherwise fail if the
local commit hasn't propagated to the remote yet). On success it prints
the launcher URL and the resolved `hf jobs uv run` command, then submits.

Inside the GPU container, `scripts/run_hf_grpo_job.py`:

- clones the Praxis repo at the pinned `PRAXIS_COMMIT` SHA,
- runs `uv run train_praxis_grpo.py ...` so the trainer's PEP 723 deps
  (`trl`, `transformers`, `unsloth`, `trackio`) are installed by uv,
- uploads `checkpoints/praxis-grpo/{run_manifest.json,metrics.csv}` to the
  configured `HF_HUB_MODEL_ID` so judges can verify the run.

`run_manifest.json` includes `wandb_url` (no-op stub today), `trackio_url`
(when `TRACKIO_SPACE_ID` is set), and `hub_model_id` (when set), giving
judges a single artifact that links every part of the run.

### HF Jobs monitor (merge verification)

Stable links (independent of a single job finishing):

- **Trackio (live):** [https://gp5901-trackio.hf.space/](https://gp5901-trackio.hf.space/)
- **Trackio Space:** [https://huggingface.co/spaces/gp5901/trackio](https://huggingface.co/spaces/gp5901/trackio)
- **Hub model (adapter + checkpoints):** [https://huggingface.co/gp5901/praxis-grpo-7b](https://huggingface.co/gp5901/praxis-grpo-7b)

Recent jobs:

| Job                                                                                       | Result                                                                                                                                                                 |
| ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`69edcfdad2c8bd8662bcfa07`](https://huggingface.co/jobs/gp5901/69edcfdad2c8bd8662bcfa07) | **Failed** — trainer import (`No module named 'mergekit'`). Fixed by declaring `mergekit` / `llm-blender` and compatible `transformers` in the trainer PEP 723 header. |
| [`69edd94dd2c8bd8662bcfb08`](https://huggingface.co/jobs/gp5901/69edd94dd2c8bd8662bcfb08) | **Good path** — reaches GRPO training loop (Trackio + Hub as above).                                                                                                   |

## Colab (`praxis_grpo_colab.ipynb`) — judge re-run

1. Open the notebook from the repo (Colab badge in [`README.md`](../README.md)).
2. **Use a GPU runtime (T4+)** and **Run all** so the default path runs **`uv run train_praxis_grpo.py`** *without* `--smoke` (short TRL GRPO: 2 steps, minimal dataset) — you get **real** `trl` / Unsloth training **loss** plus **reward** in `metrics.csv` and the generated PNGs.
3. CPU-only falls back to `--smoke` (live Space HTTP, no `GRPOTrainer`); switch to GPU for the TRL requirement.
4. Regenerate the `.ipynb` from the maintainer script after changing the contract: `python scripts/rewrite_grpo_colab_notebook.py`.

When you need long smoke curves without a TRL install, re-run a stacked smoke (raise local rate limits if you hit 429 on `/step`):

```bash
# PowerShell example (Windows)
$env:PRAXIS_RATE_LIMIT_STEP="2000/minute"
$env:PRAXIS_RATE_LIMIT_RESET="2000/minute"
python train_praxis_grpo.py --smoke --smoke-episodes 10 --steps 30 --tasks cascading-platform-failure,single-service-alert --base-url http://127.0.0.1:7860
python scripts/plot_curves.py
python scripts/build_production_evidence.py
```
