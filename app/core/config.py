import os
from typing import Optional, Literal
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    
    # Server configuration
    HOST: str = "localhost"
    PORT: int = 8000
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Storage configuration
    STORAGE_BACKEND: Literal["json", "sqlite"] = "json"  # Default to minimal version
    SQLITE_DB_PATH: str = "./data/pyqueue.db"
    JSON_STORAGE_DIR: str = "./data"
    
    # Queue configuration
    QUEUE_DATA_DIR: str = "./data"  # Legacy compatibility
    MAX_MESSAGE_SIZE: int = 256 * 1024  # 256KB
    DEFAULT_VISIBILITY_TIMEOUT: int = 30  # seconds
    MAX_RECEIVE_COUNT: int = 10
    
    # API configuration
    API_V1_PREFIX: str = "/api/v1"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create global settings instance
settings = Settings()
