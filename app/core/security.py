from fastapi import HTTPException, Depends, Header
from typing import Dict, List, Set, Optional
from enum import Enum
import secrets
import json
import os
from pathlib import Path

class QueuePermission(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    MANAGE = "manage"  # includes queue info, clear messages

class APIKeyConfig:
    def __init__(self, key: str, queues: Dict[str, List[str]], description: str = ""):
        self.key = key
        self.queues = queues  # {queue_name: [permissions]}
        self.description = description
    
    def has_permission(self, queue_name: str, permission: QueuePermission) -> bool:
        if queue_name not in self.queues:
            return False
        return permission.value in self.queues[queue_name]
    
    def get_accessible_queues(self) -> Set[str]:
        return set(self.queues.keys())

class APIKeyManager:
    def __init__(self):
        self.api_keys: Dict[str, APIKeyConfig] = {}
        self._load_api_keys()
    
    def _load_api_keys(self):
        """Load API keys from configuration"""
        # Default configuration for demonstration
        # In production, load from secure configuration file or environment variables
        api_keys_config = {
            # User 1 - Email Service
            "pk_user1_abc123def456": {
                "description": "User 1 - Email Service",
                "queues": {
                    "user1_notifications": ["read", "write", "delete", "manage"],
                    "user1_emails": ["read", "write", "delete", "manage"],
                    "shared_events": ["read"]  # Read-only access to shared queue
                }
            },
            # User 2 - Order Processing
            "pk_user2_ghi789jkl012": {
                "description": "User 2 - Order Processing",
                "queues": {
                    "user2_orders": ["read", "write", "delete", "manage"],
                    "user2_payments": ["read", "write", "delete", "manage"],
                    "shared_events": ["write"]  # Write-only access to shared queue
                }
            },
            # Service account - Limited access
            "pk_service_mno345pqr678": {
                "description": "Monitoring Service",
                "queues": {
                    "user1_notifications": ["read"],
                    "user2_orders": ["read"],
                    "monitoring_alerts": ["read", "write", "delete", "manage"]
                }
            },
            # Admin key - Full access to all queues (use with caution)
            "pk_admin_stu901vwx234": {
                "description": "Admin Access",
                "queues": {
                    "*": ["read", "write", "delete", "manage"]  # Wildcard for all queues
                }
            },
            # Development key (for testing)
            "pk_dev_12345": {
                "description": "Development Key",
                "queues": {
                    "test_queue": ["read", "write", "delete", "manage"],
                    "dev_queue": ["read", "write", "delete", "manage"]
                }
            }
        }
        
        # Try to load from external config file if it exists
        config_file = Path("config/api_keys.json")
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    external_config = json.load(f)
                    api_keys_config.update(external_config)
            except Exception as e:
                print(f"Warning: Could not load API keys from {config_file}: {e}")
        
        # Load from environment variable if set
        env_config = os.getenv("PYQUEUE_API_KEYS_JSON")
        if env_config:
            try:
                env_keys = json.loads(env_config)
                api_keys_config.update(env_keys)
            except Exception as e:
                print(f"Warning: Could not parse API keys from environment: {e}")
        
        for key, config in api_keys_config.items():
            self.api_keys[key] = APIKeyConfig(
                key=key,
                queues=config["queues"],
                description=config.get("description", "")
            )
    
    def validate_api_key(self, api_key: str) -> Optional[APIKeyConfig]:
        """Validate API key and return configuration"""
        for key, config in self.api_keys.items():
            if secrets.compare_digest(api_key, key):
                return config
        return None
    
    def check_queue_access(self, api_key_config: APIKeyConfig, queue_name: str, permission: QueuePermission) -> bool:
        """Check if API key has specific permission for queue"""
        # Check wildcard access (admin keys)
        if "*" in api_key_config.queues:
            return permission.value in api_key_config.queues["*"]
        
        return api_key_config.has_permission(queue_name, permission)

# Global instance
api_key_manager = APIKeyManager()

class QueueAccess:
    def __init__(self, api_key_config: APIKeyConfig, queue_name: str):
        self.api_key_config = api_key_config
        self.queue_name = queue_name
    
    def can_read(self) -> bool:
        return api_key_manager.check_queue_access(
            self.api_key_config, self.queue_name, QueuePermission.READ
        )
    
    def can_write(self) -> bool:
        return api_key_manager.check_queue_access(
            self.api_key_config, self.queue_name, QueuePermission.WRITE
        )
    
    def can_delete(self) -> bool:
        return api_key_manager.check_queue_access(
            self.api_key_config, self.queue_name, QueuePermission.DELETE
        )
    
    def can_manage(self) -> bool:
        return api_key_manager.check_queue_access(
            self.api_key_config, self.queue_name, QueuePermission.MANAGE
        )

def get_api_key_config(x_api_key: str = Header(..., description="API Key")) -> APIKeyConfig:
    """Dependency to validate and return API key configuration"""
    config = api_key_manager.validate_api_key(x_api_key)
    if not config:
        raise HTTPException(
            status_code=401, 
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )
    return config

def require_queue_permission(permission: QueuePermission):
    """Dependency factory for queue-specific permissions"""
    def permission_checker(
        queue_name: str,
        api_key_config: APIKeyConfig = Depends(get_api_key_config)
    ) -> QueueAccess:
        if not api_key_manager.check_queue_access(api_key_config, queue_name, permission):
            raise HTTPException(
                status_code=403, 
                detail=f"Access denied: {permission.value} permission required for queue '{queue_name}'"
            )
        return QueueAccess(api_key_config, queue_name)
    
    return permission_checker

# Optional: Dependency for operations that don't require queue-specific access
def verify_api_key(api_key_config: APIKeyConfig = Depends(get_api_key_config)) -> APIKeyConfig:
    """Simple API key validation without queue-specific checks"""
    return api_key_config
