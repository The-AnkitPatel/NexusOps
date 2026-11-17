from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nexus.api.routes import router
from nexus.config import settings

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("nexus.api.server:app", host="0.0.0.0", port=8000, reload=True)
