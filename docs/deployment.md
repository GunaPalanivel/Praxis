# Deployment

Build and run Praxis as a Docker container for local verification and Hugging
Face Spaces deployment.

---

## Build the image

From the repository root:

```bash
docker build -t praxis-env:latest .
```

---

## Run the container

```bash
docker run --rm -p 7860:7860 --name praxis-env praxis-env:latest
```

The image starts `python -m server.app` and uses these defaults:

- `HOST=0.0.0.0`
- `PORT=7860`
- `LOG_LEVEL=INFO`

---

## Smoke test the live API

```bash
curl http://localhost:7860/health
curl http://localhost:7860/tasks
curl -X POST http://localhost:7860/reset
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" -d '{}'
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" -d '{"task_name":"single-service-alert"}'
```

---

## Validate OpenEnv contract

Run validation from the repository root (with the server reachable):

```bash
openenv validate
```

---

## Hugging Face Docker Spaces checklist

1. Create a new Space with SDK set to `Docker`.
2. Push this repository with the root `Dockerfile`.
3. Ensure the app is exposed on port `7860`.
4. Confirm `POST /reset` returns HTTP `200`.
5. Tag and submit the Space according to OpenEnv instructions.

---

## Local development: training and inference

`train_praxis_grpo.py` and `inference.py` can start uvicorn on `127.0.0.1` when
`PRAXIS_URL` / `--base-url` is unreachable, **for convenience only** (use a
supervised process in shared or multi-tenant hosting). In that case stderr is
written to a temp file; the process path prints its path, and start-up failures
embed a tail of the log in the `RuntimeError` message.
