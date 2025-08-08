import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.api.routes import router
from app.core.config import settings
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Create FastAPI app
app = FastAPI(
    title="PyQueue Server",
    description="A FastAPI-based queue server for message queuing operations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

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
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
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
