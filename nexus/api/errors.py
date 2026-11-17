"""Consistent JSON error responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from nexus.agents.sql_agent import SQLGuardrailError
from nexus.logging import get_logger

logger = get_logger("nexus.api.error")


def _envelope(code: str, detail: str) -> dict[str, str]:
    return {"error": code, "detail": detail}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(SQLGuardrailError)
    async def guardrail_handler(request: Request, exc: SQLGuardrailError) -> JSONResponse:
        return JSONResponse(status_code=400, content=_envelope("guardrail_blocked", str(exc)))

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500, content=_envelope("internal_error", "Internal server error.")
        )
