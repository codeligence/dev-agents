"""Shared HTTP server that hosts all HTTP-based entrypoints (AGUI, OpenAI, etc.).

Each entrypoint registers its routes via register_router(). The server only starts
if at least one entrypoint has registered. Uvicorn lifecycle is managed here.

Note: register_router() must be called before start_service() — both happen
on the main thread during startup, so no thread-safety concern.
"""

from typing import Any
import threading

from fastapi import FastAPI
from fastapi.routing import APIRouter
import uvicorn

from core.config import get_default_config
from core.log import get_logger

logger = get_logger("HTTPServer", level="INFO")

# Shared FastAPI app — entrypoints mount their routers here
app = FastAPI(
    title="Dev Agents API",
    description="Unified HTTP API hosting AG-UI, OpenAI-compatible, and other endpoints",
)

# Number of entrypoint routers registered (default routes like /docs don't count)
_registered_count = 0


def register_router(router: APIRouter, **kwargs: Any) -> None:
    """Register a FastAPI router on the shared app.

    Args:
        router: FastAPI APIRouter to include.
        **kwargs: Passed through to app.include_router (prefix, tags, etc.).
    """
    global _registered_count
    app.include_router(router, **kwargs)
    _registered_count += 1
    logger.info(f"Registered HTTP router: prefix={kwargs.get('prefix', '/')}")


def has_routes() -> bool:
    """Check if any entrypoint registered routes."""
    return _registered_count > 0


def _setup_cors() -> None:
    """Add CORS middleware if configured via HTTP_CORS_ORIGINS env var.

    Set HTTP_CORS_ORIGINS to a comma-separated list of allowed origins,
    or "*" for unrestricted access. If unset, no CORS headers are added.
    """
    base_config = get_default_config()
    origins_raw = str(base_config.get_value("http.server.corsOrigins", "")).strip()
    if not origins_raw:
        return

    from fastapi.middleware.cors import CORSMiddleware

    origins = [o.strip() for o in origins_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(f"CORS enabled for origins: {origins}")


class HTTPServerConfig:
    """Configuration for the shared HTTP server."""

    def __init__(self) -> None:
        self._base_config = get_default_config()

    def get_host(self) -> str:
        return str(self._base_config.get_value("http.server.host", "0.0.0.0"))

    def get_port(self) -> int:
        return int(self._base_config.get_value("http.server.port", 8000))


def start_service(shutdown_event: threading.Event) -> None:
    """Start the shared HTTP server, managed by the orchestrator.

    Only starts if at least one entrypoint registered routes.

    Args:
        shutdown_event: Shared shutdown event from the orchestrator.
    """
    if not has_routes():
        logger.info("No HTTP routes registered, skipping HTTP server start")
        return

    # Set up CORS before starting
    _setup_cors()

    logger.info("Starting shared HTTP server (orchestrated)")

    try:
        server_config = HTTPServerConfig()
        host = server_config.get_host()
        port = server_config.get_port()

        logger.info(f"HTTP server starting on {host}:{port}")

        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_level="info",
        )
        server = uvicorn.Server(config)

        # Watcher thread: bridge external shutdown_event to uvicorn shutdown
        def _watch_shutdown() -> None:
            shutdown_event.wait()
            server.should_exit = True

        watcher = threading.Thread(target=_watch_shutdown, daemon=True)
        watcher.start()

        server.run()
    except Exception as e:
        logger.error(f"Error in HTTP server: {e}")
    finally:
        logger.info("HTTP server shut down")
