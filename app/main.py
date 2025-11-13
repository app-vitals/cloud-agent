"""FastAPI application."""

from fastapi import FastAPI

from app.api.tasks import router as tasks_router

app = FastAPI(
    title="Cloud Agent API",
    description="Cloud-hosted agent service that executes AI-powered development tasks",
    version="0.1.0",
)

app.include_router(tasks_router, prefix="/v1", tags=["tasks"])


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
