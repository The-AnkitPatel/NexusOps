"""Typed application settings loaded from environment / ``.env``.

Every value is overridable via an environment variable of the same name, so the
same image runs identically in local dev, CI, and Cloud Run.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM provider -------------------------------------------------------
    # Empty key => the gateway runs in deterministic offline mode (no network).
    GEMINI_API_KEY: str = ""
    NEXUS_MODEL: str = "gemini-2.5-flash"
    # Honest GenAI semantic-convention system id. This project calls the Gemini
    # Developer API (api_key auth), which is "gemini" -- NOT "vertex_ai".
    GEN_AI_SYSTEM: str = "gemini"

    # --- Service / telemetry ------------------------------------------------
    SERVICE_VERSION: str = "0.2.0"
    OTEL_SERVICE_NAME: str = "nexusops-enterprise-gateway"
    DEPLOYMENT_ENV: str = "production-fde"
    # When set (e.g. http://localhost:4318/v1/traces) spans are ALSO exported to
    # a real OTLP/HTTP collector. When empty, only the in-memory exporter runs.
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    LOG_LEVEL: str = "INFO"

    # --- Data ---------------------------------------------------------------
    DATABASE_PATH: str = "data/enterprise_tickets.db"
    POLICIES_PATH: str = "data/enterprise_policies.json"

    # --- Model pricing (USD per 1M tokens): Gemini 2.5 Flash ----------------
    COST_PER_MILLION_INPUT: float = 0.075
    COST_PER_MILLION_OUTPUT: float = 0.300


settings = Settings()
