"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.v1.router import api_router
from app.config import settings
from app.core.logging import configure_logging, get_logger

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Loan Tracker System - Manage and track loans securely",
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

# Serve static frontend files
# Try built React frontend first, fallback to simple HTML frontend
frontend_build_path = Path(__file__).parent.parent.parent / "frontend" / "dist"
static_path = Path(__file__).parent.parent / "static"

if frontend_build_path.exists():
    # Serve built React app
    app.mount("/assets", StaticFiles(directory=str(frontend_build_path / "assets")), name="assets")

    @app.get("/")
    async def serve_frontend():
        """Serve the React frontend."""
        return FileResponse(str(frontend_build_path / "index.html"))
elif static_path.exists():
    # Serve simple HTML frontend
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    @app.get("/")
    async def serve_simple_frontend():
        """Serve the simple HTML frontend."""
        return FileResponse(str(static_path / "index.html"))
else:
    @app.get("/")
    async def root():
        """Root endpoint when no frontend is available."""
        return {
            "message": "LoanTracker API is running",
            "docs": "/docs",
            "health": "/health",
            "api": "/api/v1"
        }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "storage_type": settings.storage_type,
        "encryption_enabled": settings.is_encryption_enabled,
    }


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(
        "app_started",
        app=settings.app_name,
        version=settings.app_version,
        storage=settings.storage_type,
        encryption=settings.is_encryption_enabled,
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("app_shutdown", app=settings.app_name)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.backend_reload,
    )
