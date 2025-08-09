# Storage module
from .base import StorageBackend
from .json_storage import JSONStorage
from .sqlite_storage import SQLiteStorage

def create_storage_backend(backend_type: str, **kwargs) -> StorageBackend:
    """Factory function to create storage backend instances"""
    if backend_type == "json":
        data_dir = kwargs.get("data_dir", "./data")
        return JSONStorage(data_dir)
    elif backend_type == "sqlite":
        db_path = kwargs.get("db_path", "./data/pyqueue.db")
        return SQLiteStorage(db_path)
    else:
        raise ValueError(f"Unknown storage backend: {backend_type}")

__all__ = ["StorageBackend", "JSONStorage", "SQLiteStorage", "create_storage_backend"]
