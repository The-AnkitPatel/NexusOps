from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from nexus.api.routes import router

app = FastAPI(
    title="NexusOps Enterprise Gateway",
    description="Production Forward-Deployed Multi-Agent System with OpenTelemetry & Vertex AI",
    version="0.1.0"
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
