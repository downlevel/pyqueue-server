from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import asyncio

class StorageBackend(ABC):
    """Abstract base class for storage backends following PyQueue patterns"""
    
    def __init__(self):
        self.lock = asyncio.Lock()
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the storage backend"""
        pass
    
    @abstractmethod
    async def add_message(self, queue_name: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add message to queue - async operation with proper error handling"""
        pass
    
    @abstractmethod
    async def get_messages(self, queue_name: str, limit: int = 10, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """Get messages from queue (non-destructive read) and total count for pagination"""
        pass
    
    @abstractmethod
    async def receive_messages(self, queue_name: str, max_messages: int, visibility_timeout: int) -> List[Dict[str, Any]]:
        """Receive messages with SQS-style visibility timeout"""
        pass
    
    @abstractmethod
    async def delete_message(self, queue_name: str, receipt_handle: str) -> bool:
        """Delete message by receipt handle"""
        pass
    
    @abstractmethod
    async def delete_message_by_id(self, queue_name: str, message_id: str) -> bool:
        """Delete message by ID"""
        pass
    
    @abstractmethod
    async def update_message(self, queue_name: str, message_id: str, new_message_body: Dict[str, Any]) -> bool:
        """Update message data"""
        pass
    
    @abstractmethod
    async def clear_queue(self, queue_name: str) -> int:
        """Clear all messages from queue, return count of deleted messages"""
        pass
    
    @abstractmethod
    async def get_queue_info(self, queue_name: str) -> Dict[str, Any]:
        """Get queue information and statistics"""
        pass
    
    @abstractmethod
    async def list_queues(self) -> List[str]:
        """List all available queues"""
        pass
    
    @abstractmethod
    async def health_check(self, queue_name: Optional[str] = None) -> bool:
        """Check if the storage backend is healthy"""
        pass
