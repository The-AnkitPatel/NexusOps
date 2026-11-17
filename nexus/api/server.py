"""FastAPI application: lifespan, middleware, metrics, and error handling."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from nexus.api.errors import register_error_handlers
from nexus.api.routes import router
from nexus.config import settings
from nexus.logging import get_logger
from nexus.telemetry import prometheus
from nexus.telemetry.tracer import provider

logger = get_logger("nexus.api.access")

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("gateway starting (version=%s)", settings.SERVICE_VERSION)
    yield
    provider.shutdown()  # flush pending OTel spans on shutdown


app = FastAPI(
    title="NexusOps Enterprise Gateway",
    description=(
        "Multi-agent gateway: hybrid retrieval, read-only SQL planning, grounding "
        "guardrails, and OpenTelemetry telemetry."
    ),
    version=settings.SERVICE_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # credentials must stay off with a wildcard origin (browsers reject the combo).
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    response = await call_next(request)
    duration_s = time.perf_counter() - start

    route = request.scope.get("route")
    path = route.path if route is not None else request.url.path
    prometheus.observe(request.method, path, response.status_code, duration_s)

    response.headers["X-Request-ID"] = request_id
    for key, value in _SECURITY_HEADERS.items():
        response.headers[key] = value
    logger.info(
        "%s %s -> %s (%.1fms) rid=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_s * 1000.0,
        request_id,
    )
    return response


register_error_handlers(app)
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("nexus.api.server:app", host="0.0.0.0", port=8000, reload=True)
