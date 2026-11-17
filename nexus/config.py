from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

class Settings(BaseSettings):
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", "")
    NEXUS_MODEL: str = os.getenv("NEXUS_MODEL", "gemini-2.5-flash")
    OTEL_SERVICE_NAME: str = os.getenv("OTEL_SERVICE_NAME", "nexusops-enterprise-gateway")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/enterprise_tickets.db")
    POLICIES_PATH: str = os.getenv("POLICIES_PATH", "data/enterprise_policies.json")
    
    # Model pricing per 1 Million tokens (USD)
    COST_PER_MILLION_INPUT: float = 0.075   # Gemini 2.5 Flash input
    COST_PER_MILLION_OUTPUT: float = 0.300  # Gemini 2.5 Flash output

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
