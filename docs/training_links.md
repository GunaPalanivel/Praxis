# Training Links

Run date: 2026-04-26

- Trackio: not configured in this local environment (no project credentials available).
- WandB: not configured in this local environment (no API key available).
- Local run manifest: `checkpoints/praxis-grpo/run_manifest.json`
- Local metrics CSV: `checkpoints/praxis-grpo/metrics.csv`

When credentials are available, re-run:

```bash
python train_praxis_grpo.py --steps 50 --tasks cascading-platform-failure,single-service-alert --model qwen-7b
```
