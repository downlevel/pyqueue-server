import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.api.routes import router
from app.core.config import settings
from app.services.queue_service import initialize_queue_service, get_queue_service
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PyQueue Server",
    description="A FastAPI-based queue server with configurable storage backends (JSON/SQLite)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup"""
    logger.info(f"Starting PyQueue Server with {settings.STORAGE_BACKEND} storage backend")
    
    try:
        # Initialize the queue service with the configured storage backend
        await initialize_queue_service()
        logger.info("Queue service initialized successfully")
        
        # Test storage backend health
        queue_service = get_queue_service()
        is_healthy = await queue_service.health_check()
        if is_healthy:
            logger.info("Storage backend health check passed")
        else:
            logger.warning("Storage backend health check failed")
            
    except Exception as e:
        logger.error(f"Failed to initialize queue service: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("PyQueue Server shutting down")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")

@app.get("/")
async def root():
    """Root endpoint with basic server information"""
    return {
        "message": "PyQueue Server",
        "version": "1.0.0",        "docs": "/docs",
        "health": "/api/v1/health",
        "storage_backend": settings.STORAGE_BACKEND,
        "security": {
            "authentication": "API Key required",
            "auth_header": "X-API-Key",
            "user_info": "/api/v1/auth/me",
            "permissions": "/api/v1/auth/permissions/{queue_name}"
        }
    }

@app.get("/health")
async def health_check():
    """Global health check endpoint"""
    return {"status": "healthy", "service": "pyqueue-server"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
