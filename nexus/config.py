"""Typed application settings loaded from environment / ``.env``.

Every value is overridable via an environment variable of the same name, so the
same image runs identically in local dev, CI, and Cloud Run.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM provider -------------------------------------------------------
    # Empty => offline mode (no network).
    GEMINI_API_KEY: str = ""
    NEXUS_MODEL: str = "gemini-2.5-flash"
    # GenAI semconv system id: "gemini" (Developer API) or "vertex_ai".
    GEN_AI_SYSTEM: str = "gemini"

    # --- Service / telemetry ------------------------------------------------
    SERVICE_VERSION: str = "0.5.0"
    OTEL_SERVICE_NAME: str = "nexusops-enterprise-gateway"
    DEPLOYMENT_ENV: str = "production-fde"
    # Set to an OTLP/HTTP collector URL (e.g. http://localhost:4318/v1/traces).
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    LOG_LEVEL: str = "INFO"

    # --- Data ---------------------------------------------------------------
    DATABASE_PATH: str = "data/enterprise_tickets.db"
    POLICIES_PATH: str = "data/enterprise_policies.json"

    # --- Model pricing (USD per 1M tokens): Gemini 2.5 Flash ----------------
    COST_PER_MILLION_INPUT: float = 0.075
    COST_PER_MILLION_OUTPUT: float = 0.300


settings = Settings()
