# Configuration

Praxis currently has a small runtime configuration surface.

---

## Current server settings

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Python logging level for the FastAPI server |

Example:

```bash
LOG_LEVEL=DEBUG python -m uvicorn server.app:app --host 0.0.0.0 --port 7860
```

---

## Current runtime conventions

- The docs and examples assume the server is running on port `7860`.
- Port selection currently comes from the `uvicorn` command you run locally.
- Observation payloads are ASCII-normalized by the server; no environment
  variable is needed to enable that behavior.

---

## Planned submission variables

These variables are part of later submission phases and are **not** consumed by
the current server implementation:

| Variable | Planned use |
|---|---|
| `HF_TOKEN` | API key for the future baseline agent |
| `API_BASE_URL` | OpenAI-compatible inference endpoint for the future baseline |
| `MODEL_NAME` | Model identifier for the future baseline |

Until `inference.py` is added, they should be treated as reserved future config,
not active runtime requirements.
