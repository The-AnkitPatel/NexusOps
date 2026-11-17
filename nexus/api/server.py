import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from nexus.api.routes import router
from nexus.config import settings
from nexus.logging import get_logger

logger = get_logger("nexus.api.access")

app = FastAPI(
    title="NexusOps Enterprise Gateway",
    description=(
        "Forward-Deployed multi-agent gateway: hybrid retrieval (BM25 + TF-IDF "
        "via RRF), read-only SQL planning, grounding guardrails, and "
        "OpenTelemetry GenAI telemetry."
    ),
    version=settings.SERVICE_VERSION,
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
    """Attach a request id and emit a structured access log per request."""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "%s %s -> %s (%sms) rid=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )
    return response


app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("nexus.api.server:app", host="0.0.0.0", port=8000, reload=True)
