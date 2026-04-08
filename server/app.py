"""
server.app — FastAPI application factory.

Builds the HTTP API that the validation script, inference.py, and
HuggingFace Spaces will call.

Endpoints:
    POST /reset    → Start a new episode
    POST /step     → Execute one action
    GET  /state    → Get current episode state
    GET  /tasks    → List available task names
    GET  /health   → Health check (returns 200 + metadata)
    GET  /         → Web UI redirect / info

Environment Variables:
    ENABLE_WEB_INTERFACE: "true" to enable OpenEnv web UI (optional)
    LOG_LEVEL: log level — default "INFO"
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from praxis_env.models import PraxisAction
from server.praxis_environment import PraxisEnvironment

# ── Logging ───────────────────────────────────────────────────────────────────

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Global environment instance ────────────────────────────────────────────────

env = PraxisEnvironment()


# ── Request / Response schemas (Pydantic, for FastAPI validation) ─────────────

class ResetRequest(BaseModel):
    """POST /reset body."""
    task_name: str = "single-service-alert"


class StepRequest(BaseModel):
    """POST /step body."""
    command: str


# ── App factory ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Praxis environment server starting up")
    logger.info("Available tasks: %s", env.list_tasks())
    yield
    logger.info("Praxis environment server shutting down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Praxis — Production Incident Response Environment",
        description=(
            "OpenEnv-compatible environment for training AI agents on "
            "SRE on-call triage tasks. Implements reset/step/state API."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS — allow judges and web UI to call from any origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.get("/health")
    async def health() -> dict[str, Any]:
        """Health check — must return 200 for the pre-validation script."""
        return {
            "status": "ok",
            "environment": "praxis-env",
            "version": "1.0.0",
            "available_tasks": env.list_tasks(),
        }

    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint — basic info for judges browsing the space."""
        return {
            "name": "praxis-env",
            "description": "Production Incident Response Training Ground",
            "docs": "/docs",
            "health": "/health",
            "tasks": "/tasks",
        }

    @app.post("/reset")
    async def reset(request: Optional[ResetRequest] = None) -> dict[str, Any]:
        """
        Start a new episode.

        Body: {"task_name": "single-service-alert"}
        Returns: PraxisObservation as JSON
        """
        task = (request.task_name if request else None) or "single-service-alert"
        try:
            obs = env.reset(task_name=task)
            return PraxisEnvironment._obs_to_dict(obs)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.exception("reset() failed: %s", e)
            raise HTTPException(status_code=500, detail=f"reset() error: {e}")

    @app.post("/step")
    async def step(request: StepRequest) -> dict[str, Any]:
        """
        Execute one action.

        Body: {"command": "query_logs service=auth timerange=5m"}
        Returns: {observation, reward, done, info}
        """
        try:
            action = PraxisAction(command=request.command)
            result = env.step(action)
            return result
        except RuntimeError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.exception("step() failed: %s", e)
            raise HTTPException(status_code=500, detail=f"step() error: {e}")

    @app.get("/state")
    async def state() -> dict[str, Any]:
        """
        Get current episode state.

        Returns: PraxisState as JSON
        """
        try:
            s = env.state()
            return {
                "episode_id": s.episode_id,
                "step_count": s.step_count,
                "task_name": s.task_name,
                "incident_resolved": s.incident_resolved,
                "root_cause_identified": s.root_cause_identified,
                "cumulative_reward": s.cumulative_reward,
            }
        except RuntimeError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/tasks")
    async def tasks() -> dict[str, list[str]]:
        """List all available task names."""
        return {"tasks": env.list_tasks()}

    return app


def main() -> None:
    """Run the API server via uvicorn.

    Exposed as the `server` project script so validators and local runners
    can start the environment without custom commands.
    """
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(
        "server.app:app",
        host=host,
        port=port,
        log_level=LOG_LEVEL.lower(),
    )


# ── ASGI app (imported by uvicorn and Dockerfile CMD) ─────────────────────────
app = create_app()


if __name__ == "__main__":
    main()
