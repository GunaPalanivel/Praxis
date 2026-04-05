# Configuration

Praxis currently has a small runtime configuration surface.

---

## Current server settings

| Variable    | Default   | Description                                 |
| ----------- | --------- | ------------------------------------------- |
| `HOST`      | `0.0.0.0` | Host interface used by `server.app:main`    |
| `PORT`      | `7860`    | Server port used by `server.app:main`       |
| `LOG_LEVEL` | `INFO`    | Python logging level for the FastAPI server |

Example:

```bash
LOG_LEVEL=DEBUG python -m uvicorn server.app:app --host 0.0.0.0 --port 7860
```

When running through the project script entrypoint:

```bash
HOST=0.0.0.0 PORT=7860 LOG_LEVEL=INFO server
```

---

## Current runtime conventions

- The docs and examples assume the server is running on port `7860`.
- Port selection comes from your `uvicorn` flags or the `PORT` env var used by
  `server.app:main`.
- Observation payloads are ASCII-normalized by the server; no environment
  variable is needed to enable that behavior.

---

## Container runtime defaults

The root `Dockerfile` sets these defaults:

- `HOST=0.0.0.0`
- `PORT=7860`
- `LOG_LEVEL=INFO`

Override them at runtime if needed, for example:

```bash
docker run --rm -p 7860:7860 -e LOG_LEVEL=DEBUG praxis-env:latest
```

---

## Baseline inference variables

These variables are consumed by the root `inference.py` baseline script:

| Variable                     | Current use                                                                     |
| ---------------------------- | ------------------------------------------------------------------------------- |
| `HF_TOKEN`                   | Primary API key for OpenAI client calls in baseline inference                   |
| `OPENAI_API_KEY` / `API_KEY` | Compatibility fallback key if `HF_TOKEN` is unset                               |
| `API_BASE_URL`               | OpenAI-compatible inference endpoint for baseline inference                     |
| `MODEL_NAME`                 | Model identifier for baseline inference                                         |
| `PRAXIS_URL`                 | Praxis server URL consumed by baseline script (default `http://127.0.0.1:7860`) |
| `PRAXIS_TASKS`               | Optional comma-separated subset of tasks to run                                 |

Minimal local baseline run:

```bash
PRAXIS_URL=http://127.0.0.1:7860 python inference.py
```
