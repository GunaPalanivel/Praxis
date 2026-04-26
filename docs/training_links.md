# Training Links

Run date: 2026-04-26

- Plotting / evidence scripts (`scripts/build_production_evidence.py`, `scripts/plot_curves.py`, `scripts/generate_grpo_evidence.py`) need the **`evidence`** optional extra. With uv: `uv sync --all-extras` (includes `evidence`) or `uv sync --extra evidence`.
- Trackio: not configured in this local environment (no project credentials available).
- WandB: not configured in this local environment (no API key available).
- Local run manifest: `checkpoints/praxis-grpo/run_manifest.json`
- Local metrics CSV: `checkpoints/praxis-grpo/metrics.csv`
- Rollout baseline log: `docs/rollout_baseline.txt`
- Rollout trained log: `docs/rollout_trained.txt`
- Rollout comparison plot: `docs/rollout_compare.png`
- Evolution summary: `docs/training_evolution.md`
- Long smoke refresh on this date: 170 logged rows in `checkpoints/praxis-grpo/metrics.csv` (stacked episodes via `python train_praxis_grpo.py --smoke --smoke-episodes 10 --steps 30 ...`)

When credentials are available, re-run:

```bash
python train_praxis_grpo.py --steps 50 --tasks cascading-platform-failure,single-service-alert --model qwen-7b
```

When you need long smoke curves without a TRL install, re-run a stacked smoke (raise local rate limits if you hit 429 on `/step`):

```bash
# PowerShell example (Windows)
$env:PRAXIS_RATE_LIMIT_STEP="2000/minute"
$env:PRAXIS_RATE_LIMIT_RESET="2000/minute"
python train_praxis_grpo.py --smoke --smoke-episodes 10 --steps 30 --tasks cascading-platform-failure,single-service-alert --base-url http://127.0.0.1:7860
python scripts/plot_curves.py
python scripts/build_production_evidence.py
```
