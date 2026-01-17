import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone

from app.models.queue import QueueMessage, MessageStatus, QueueInfo
from app.core.config import settings
from app.core.storage import create_storage_backend, StorageBackend

logger = logging.getLogger(__name__)


class QueueService:
    """Service for managing queue operations with configurable storage backends"""
    
    def __init__(self, storage_backend: Optional[StorageBackend] = None):
        if storage_backend:
            self.storage = storage_backend
        else:
            # Create storage backend based on configuration
            if settings.STORAGE_BACKEND == "sqlite":
                self.storage = create_storage_backend("sqlite", db_path=settings.SQLITE_DB_PATH)
            else:
                self.storage = create_storage_backend("json", data_dir=settings.JSON_STORAGE_DIR)
    
    async def initialize(self):
        """Initialize the storage backend"""
        await self.storage.initialize()
    
    async def add_message(self, queue_name: str, message_body: Dict, message_id: Optional[str] = None) -> str:
        """Add a message to the queue"""
        message_data = {
            "message_body": message_body,
            "attributes": {},
        }
        
        if message_id:
            message_data["id"] = message_id
            message_data["message_id"] = message_id
        
        result = await self.storage.add_message(queue_name, message_data)
        return result.get("message_id") or result.get("id")
    
    async def get_messages(self, queue_name: str, limit: int = 10, offset: int = 0) -> Tuple[List[QueueMessage], int]:
        """Get messages from the queue (without making them invisible) with pagination support"""
        messages_data, total = await self.storage.get_messages(queue_name, limit, offset)
        messages = [self._convert_to_queue_message(msg_data) for msg_data in messages_data]
        return messages, total
    
    async def receive_messages(
        self,
        queue_name: str,
        max_messages: int = 10,
        visibility_timeout: int = 30,
        consumer_id: Optional[str] = None,
        remove_after_receive: bool = False,
        only_new: bool = False
    ) -> List[QueueMessage]:
        """Receive messages with optional consumer filtering, auto removal, and new-message filtering"""
        messages_data = await self.storage.receive_messages(
            queue_name,
            max_messages,
            visibility_timeout,
            consumer_id=consumer_id,
            remove_after_receive=remove_after_receive,
            only_new=only_new
        )
        return [self._convert_to_queue_message(msg_data) for msg_data in messages_data]
    
    async def delete_message(self, queue_name: str, receipt_handle: str) -> bool:
        """Delete a message using receipt handle"""
        return await self.storage.delete_message(queue_name, receipt_handle)
    
    async def delete_message_by_id(self, queue_name: str, message_id: str) -> bool:
        """Delete a message by its ID"""
        return await self.storage.delete_message_by_id(queue_name, message_id)
    
    async def update_message(self, queue_name: str, message_id: str, new_message_body: Dict) -> bool:
        """Update a message's content"""
        return await self.storage.update_message(queue_name, message_id, new_message_body)
    
    async def clear_queue(self, queue_name: str) -> int:
        """Clear all messages from the queue"""
        return await self.storage.clear_queue(queue_name)
    
    async def get_message_by_id(self, queue_name: str, message_id: str) -> Optional[QueueMessage]:
        """Get a specific message by its ID"""
        msg_data = await self.storage.get_message_by_id(queue_name, message_id)
        if msg_data:
            return self._convert_to_queue_message(msg_data)
        return None
    
    async def check_messages_existence(self, queue_name: str, message_ids: List[str]) -> List[str]:
        """Check which messages from the list exist in the queue"""
        # Optimized implementation could rely on storage backend specific method
        # For now, we iterate, but it happens locally on the server (fast)
        existing_ids = []
        for msg_id in message_ids:
            if await self.storage.get_message(queue_name, msg_id):
                existing_ids.append(msg_id)
        return existing_ids

    async def get_queue_info(self, queue_name: str) -> QueueInfo:
        """Get information about the queue"""
        info_data = await self.storage.get_queue_info(queue_name)
        
        if not info_data.get("exists", True):
            # Queue doesn't exist - return default info
            return QueueInfo(
                queue_name=queue_name,
                message_count=0,
                available_messages=0,
                in_flight_messages=0,
                queue_size_bytes=0,
                created_timestamp=datetime.now(timezone.utc),
                last_modified=datetime.now(timezone.utc)
            )
        
        # Convert storage data to QueueInfo model
        created_timestamp = self._parse_datetime(info_data.get("created_at"))
        last_modified = self._parse_datetime(info_data.get("last_modified"))
        
        return QueueInfo(
            queue_name=queue_name,
            message_count=info_data.get("total_messages", 0),
            available_messages=info_data.get("available_messages", 0),
            in_flight_messages=info_data.get("in_flight_messages", 0),
            queue_size_bytes=info_data.get("queue_size_bytes", 0),
            created_timestamp=created_timestamp,
            last_modified=last_modified
        )
    
    async def list_queues(self) -> List[str]:
        """List all available queues"""
        return await self.storage.list_queues()
    
    async def health_check(self, queue_name: Optional[str] = None) -> bool:
        """Check if the queue service is healthy"""
        return await self.storage.health_check(queue_name)
    
    def _convert_to_queue_message(self, msg_data: Dict[str, Any]) -> QueueMessage:
        """Convert storage message data to QueueMessage model"""
        # Handle timestamp conversion
        timestamp = self._parse_datetime(msg_data.get("timestamp"))
        
        # Handle visibility timeout
        visibility_timeout = None
        if msg_data.get("visibility_timeout_until"):
            visibility_timeout = self._parse_datetime(msg_data["visibility_timeout_until"])
        elif msg_data.get("visibility_timeout"):
            visibility_timeout = self._parse_datetime(msg_data["visibility_timeout"])
        
        # Handle message status
        status = MessageStatus.AVAILABLE
        if msg_data.get("status") == "in_flight":
            status = MessageStatus.IN_FLIGHT
        elif msg_data.get("status") == "processed":
            status = MessageStatus.PROCESSED
        
        return QueueMessage(
            id=msg_data.get("message_id") or msg_data.get("id"),
            message_body=msg_data.get("message_body", {}),
            timestamp=timestamp,
            status=status,
            visibility_timeout=visibility_timeout,
            receipt_handle=msg_data.get("receipt_handle"),
            receive_count=msg_data.get("receive_count", 0),
            attributes=msg_data.get("attributes", {})
        )
    
    def _parse_datetime(self, dt_value: Any) -> datetime:
        """Parse datetime from various formats"""
        if isinstance(dt_value, datetime):
            return dt_value
        elif isinstance(dt_value, str):
            try:
                # Handle ISO format with or without timezone
                if dt_value.endswith('Z'):
                    dt_value = dt_value.replace('Z', '+00:00')
                return datetime.fromisoformat(dt_value)
            except ValueError:
                # Fallback to current time if parsing fails
                logger.warning(f"Failed to parse datetime: {dt_value}")
                return datetime.now(timezone.utc)
        else:
            return datetime.now(timezone.utc)


# Global queue service instance
_queue_service: Optional[QueueService] = None


async def initialize_queue_service(storage_backend: Optional[StorageBackend] = None) -> None:
    """Initialize the global queue service instance"""
    global _queue_service
    _queue_service = QueueService(storage_backend)
    await _queue_service.initialize()
    logger.info(f"Queue service initialized with {settings.STORAGE_BACKEND} storage backend")


def get_queue_service() -> QueueService:
    """Get the global queue service instance"""
    if _queue_service is None:
        raise RuntimeError("Queue service not initialized. Call initialize_queue_service() first.")
    return _queue_service

# Legacy compatibility - for backwards compatibility during transition
queue_service = None  # Will be set by initialize_queue_service
