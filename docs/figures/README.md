# Judge and publication figures

All committed training and evidence plots for **README**, blog, and hackathon deliverables live here so paths are stable and easy to find.

| File                                               | Purpose                                                           |
| -------------------------------------------------- | ----------------------------------------------------------------- |
| [`rollout_compare.png`](rollout_compare.png)       | Before/after per-step reward (baseline vs trained inference logs) |
| [`reward_curve.png`](reward_curve.png)             | Training mean reward (e.g. from `train_praxis_grpo` / Colab)      |
| [`loss_curve.png`](loss_curve.png)                 | Training loss / GRPO objective curve                              |
| [`rubric_attribution.png`](rubric_attribution.png) | Mean per-rubric score from `metrics.csv` (optional)               |
| `*_sample_run.png`, `loss_curve_smoke.png`         | Ad hoc local run outputs (if present)                             |

**Generate / refresh**

- `python scripts/plot_curves.py` — writes reward, loss, and rubric charts here (see defaults in that script).
- `python scripts/generate_grpo_evidence.py` — Colab-style discrete policy (writes here when run from repo root).
- `python scripts/build_production_evidence.py` — builds `rollout_compare.png` from `docs/rollout_*.txt` and checkpoint CSV.

Relative links from the repo root use the prefix `docs/figures/`.

Ad hoc Colab or one-off run exports (extra logs, traces, run-specific plots) live in **[`colabresults/`](../../colabresults/README.md)** at the repository root (instantly visible in the file tree).
