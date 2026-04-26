# Colab / training run exports (`colabresults/`)

This folder is at the **repository root** so Colab and training run artifacts are easy to spot. Ad hoc results from a Colab or local run (curves, logs, rollouts) go here.

| File | Description |
| ---- | ------------ |
| `reward_curve.png` | Reward comparison plot (baseline vs trained) |
| `loss_curve.png` | Training / policy loss curve |
| `praxis_training_log.jsonl` | Per-step or per-line training log |
| `praxis_training_summary.csv` | Tabular run summary |
| `eval_checkpoints.json` | Checkpoint / eval metadata for runs |
| `rollout_trace.txt` | Text rollout trace (e.g. `[STEP]` lines) |

Regenerate or replace these when you re-run; they are not required for `pytest` or `openenv validate`.

See also: [`docs/figures/README.md`](../docs/figures/README.md) for committed judge figure defaults.
