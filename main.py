"""
FastAPI application entry point for Chat with PDF system.
"""
from fastapi import FastAPI
from api.routes.file_router import files_router
from api.routes.webhook_router import webhook_router
from core.handlers import register_exception_handlers

app = FastAPI(
    title="Chat with PDF",
    description="Hybrid-Inline PDF + RAG Chat System",
    version="0.1.0"
)

# Register global exception handlers
register_exception_handlers(app)

# Include routers
app.include_router(files_router)
app.include_router(webhook_router)


@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "message": "Chat with PDF API",
        "status": "running",
        "version": "0.1.0"
    }
