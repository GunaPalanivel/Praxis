# Praxis Documentation

Current development docs for the Praxis incident-response environment.

This documentation set describes the repository as it exists today:

- FastAPI server with `POST /reset`, `POST /step`, `GET /state`, `GET /tasks`, and `GET /health`
- Two implemented tasks: `single-service-alert` and `cascading-failure`
- ASCII-normalized observation text for stable local console output
- Signed per-step rewards in `[-1.0, 1.0]`

Planned later phases still include the hard third task, a root submission `README.md`,
`inference.py`, Docker packaging, and a centralized reward module.

---

## Documentation Index

| Guide | Description |
|---|---|
| [Getting Started](./getting-started.md) | Install the repo, run the server, and play a first episode |
| [Action Space](./action-space.md) | Command grammar and supported agent actions |
| [Observation Space](./observation-space.md) | Observation fields and current response semantics |
| [Tasks](./tasks.md) | Current task catalog: 2 implemented tasks and 1 planned task |
| [API Reference](./api-reference.md) | HTTP endpoint contracts for the current server |
| [Configuration](./configuration.md) | Current runtime settings and planned submission variables |
| [Contributing](./contributing.md) | How to add scenarios, update docs, and extend tests |

---

## What is Praxis?

Praxis is an OpenEnv-style environment for training AI agents on production
incident response. The agent receives an incident alert, inspects logs and
metrics, checks service dependencies, and then decides whether to diagnose,
remediate, or escalate.

The current repo focuses on the first four implementation phases:

- Phase 1-2: environment models, parser, server routes, and lifecycle
- Phase 3: `single-service-alert`
- Phase 4: `cascading-failure`

If you need the live contract, use the code and passing tests as the source of
truth, then use these docs as the synced explanation of that state.
