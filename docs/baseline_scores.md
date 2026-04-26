# Baseline Scores (Outcome x Efficiency)

Run date: 2026-04-26
Task: `cascading-platform-failure` (5 seeded runs, seeds `2026..2030`)

| Agent | Mean score (outcome x efficiency) | Behaviour |
| --- | ---: | --- |
| Random baseline | 0.038 | Randomized valid commands from task command pool; often partial progress but inconsistent closure. |
| Qwen2.5-72B (no system prompt) | 0.038 | No-prompt mode falls back to random policy when no API token is configured; mirrors random baseline. |
| Qwen2.5-72B (SRE MissionOps prompt) | 0.904 | SRE mode uses the deterministic SRE fallback policy and consistently executes full diagnosis/remediation/report path. |

Sanity run (`single-service-alert`, 1 seeded run): mean score `0.469`.

## Reproduction commands

```bash
PRAXIS_URL=http://127.0.0.1:7872 PRAXIS_RATE_LIMIT_DEFAULT=100000/minute PRAXIS_RATE_LIMIT_STEP=100000/minute PRAXIS_RATE_LIMIT_RESET=100000/minute python inference.py --task cascading-platform-failure --runs 5 --seed 2026 --model random
PRAXIS_URL=http://127.0.0.1:7873 PRAXIS_RATE_LIMIT_DEFAULT=100000/minute PRAXIS_RATE_LIMIT_STEP=100000/minute PRAXIS_RATE_LIMIT_RESET=100000/minute python inference.py --task cascading-platform-failure --runs 5 --seed 2026 --no-system-prompt
PRAXIS_URL=http://127.0.0.1:7874 PRAXIS_RATE_LIMIT_DEFAULT=100000/minute PRAXIS_RATE_LIMIT_STEP=100000/minute PRAXIS_RATE_LIMIT_RESET=100000/minute python inference.py --task cascading-platform-failure --runs 5 --seed 2026 --system-prompt sre
PRAXIS_URL=http://127.0.0.1:7875 PRAXIS_RATE_LIMIT_DEFAULT=100000/minute PRAXIS_RATE_LIMIT_STEP=100000/minute PRAXIS_RATE_LIMIT_RESET=100000/minute python inference.py --task single-service-alert --runs 1 --seed 2026 --system-prompt sre
```
