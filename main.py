"""
FastAPI application entry point for Chat with PDF system.
"""
from fastapi import FastAPI

app = FastAPI(
    title="Chat with PDF",
    description="Hybrid-Inline PDF + RAG Chat System",
    version="0.1.0"
)


@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "message": "Chat with PDF API",
        "status": "running",
        "version": "0.1.0"
    }
