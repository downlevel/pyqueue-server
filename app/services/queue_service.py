import json
import os
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from pathlib import Path
import aiofiles
import logging

from app.models.queue import QueueMessage, MessageStatus, QueueInfo
from app.core.config import settings

logger = logging.getLogger(__name__)

class QueueService:
    """Service for managing queue operations"""
    
    def __init__(self):
        self.data_dir = Path(settings.QUEUE_DATA_DIR)
        self.data_dir.mkdir(exist_ok=True)
        self._queues: Dict[str, Dict] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
    
    def _get_queue_file(self, queue_name: str) -> Path:
        """Get the file path for a queue"""
        return self.data_dir / f"{queue_name}.json"
    
    def _get_lock(self, queue_name: str) -> asyncio.Lock:
        """Get or create a lock for a queue"""
        if queue_name not in self._locks:
            self._locks[queue_name] = asyncio.Lock()
        return self._locks[queue_name]
    
    async def _load_queue(self, queue_name: str) -> List[QueueMessage]:
        """Load queue from file"""
        queue_file = self._get_queue_file(queue_name)
        
        if not queue_file.exists():
            return []
        
        try:
            async with aiofiles.open(queue_file, 'r') as f:
                content = await f.read()
                if not content.strip():
                    return []
                
                data = json.loads(content)
                messages = []
                for item in data:
                    # Convert timestamp strings back to datetime objects
                    if isinstance(item.get('timestamp'), str):
                        item['timestamp'] = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
                    if isinstance(item.get('visibility_timeout'), str):
                        item['visibility_timeout'] = datetime.fromisoformat(item['visibility_timeout'].replace('Z', '+00:00'))
                    
                    messages.append(QueueMessage(**item))
                return messages
        except json.JSONDecodeError as e:
            logger.error(f"Error loading queue {queue_name}: {e}")
            return []
    
    async def _save_queue(self, queue_name: str, messages: List[QueueMessage]):
        """Save queue to file"""
        queue_file = self._get_queue_file(queue_name)
        
        try:
            # Convert messages to dict for JSON serialization
            data = []
            for msg in messages:
                msg_dict = msg.model_dump()
                # Ensure datetime objects are properly serialized
                if isinstance(msg_dict.get('timestamp'), datetime):
                    msg_dict['timestamp'] = msg_dict['timestamp'].isoformat()
                if isinstance(msg_dict.get('visibility_timeout'), datetime):
                    msg_dict['visibility_timeout'] = msg_dict['visibility_timeout'].isoformat()
                data.append(msg_dict)
            
            async with aiofiles.open(queue_file, 'w') as f:
                await f.write(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.error(f"Error saving queue {queue_name}: {e}")
            raise
    
    def _generate_receipt_handle(self) -> str:
        """Generate a unique receipt handle"""
        return f"receipt_{uuid.uuid4().hex}"
    
    async def add_message(self, queue_name: str, message_body: Dict, message_id: Optional[str] = None) -> str:
        """Add a message to the queue"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            if message_id is None:
                message_id = str(uuid.uuid4())
            
            # Check if message already exists
            if any(msg.id == message_id for msg in messages):
                logger.warning(f"Message {message_id} already exists in queue {queue_name}")
                return message_id
            
            new_message = QueueMessage(
                id=message_id,
                message_body=message_body,
                timestamp=datetime.now(timezone.utc)
            )
            
            messages.append(new_message)
            await self._save_queue(queue_name, messages)
            
            logger.info(f"Added message {message_id} to queue {queue_name}")
            return message_id
    
    async def get_messages(self, queue_name: str, max_messages: int = 10) -> List[QueueMessage]:
        """Get messages from the queue (without making them invisible)"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            # Filter available messages
            available_messages = [
                msg for msg in messages 
                if msg.status == MessageStatus.AVAILABLE
            ]
            
            return available_messages[:max_messages]
    
    async def receive_messages(self, queue_name: str, max_messages: int = 10, visibility_timeout: int = 30) -> List[QueueMessage]:
        """Receive messages (SQS-style with visibility timeout)"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            # Find available messages
            available_messages = []
            now = datetime.now(timezone.utc)
            
            for msg in messages:
                if (msg.status == MessageStatus.AVAILABLE or 
                    (msg.status == MessageStatus.IN_FLIGHT and 
                     msg.visibility_timeout and msg.visibility_timeout <= now)):
                    available_messages.append(msg)
                    
                    if len(available_messages) >= max_messages:
                        break
            
            # Mark messages as in-flight and set visibility timeout
            for msg in available_messages:
                msg.status = MessageStatus.IN_FLIGHT
                msg.visibility_timeout = now + timedelta(seconds=visibility_timeout)
                msg.receipt_handle = self._generate_receipt_handle()
                msg.receive_count += 1
            
            await self._save_queue(queue_name, messages)
            return available_messages
    
    async def delete_message(self, queue_name: str, receipt_handle: str) -> bool:
        """Delete a message using receipt handle"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            # Find message with matching receipt handle
            for i, msg in enumerate(messages):
                if msg.receipt_handle == receipt_handle:
                    messages.pop(i)
                    await self._save_queue(queue_name, messages)
                    logger.info(f"Deleted message with receipt handle {receipt_handle} from queue {queue_name}")
                    return True
            
            return False
    
    async def delete_message_by_id(self, queue_name: str, message_id: str) -> bool:
        """Delete a message by its ID"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            # Find message with matching ID
            for i, msg in enumerate(messages):
                if msg.id == message_id:
                    messages.pop(i)
                    await self._save_queue(queue_name, messages)
                    logger.info(f"Deleted message {message_id} from queue {queue_name}")
                    return True
            
            return False
    
    async def update_message(self, queue_name: str, message_id: str, new_message_body: Dict) -> bool:
        """Update a message's content"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            # Find message with matching ID
            for msg in messages:
                if msg.id == message_id:
                    msg.message_body = new_message_body
                    msg.timestamp = datetime.now(timezone.utc)  # Update timestamp
                    await self._save_queue(queue_name, messages)
                    logger.info(f"Updated message {message_id} in queue {queue_name}")
                    return True
            
            return False
    
    async def clear_queue(self, queue_name: str) -> bool:
        """Clear all messages from the queue"""
        async with self._get_lock(queue_name):
            await self._save_queue(queue_name, [])
            logger.info(f"Cleared queue {queue_name}")
            return True
    
    async def get_queue_info(self, queue_name: str) -> QueueInfo:
        """Get information about the queue"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            available_count = sum(1 for msg in messages if msg.status == MessageStatus.AVAILABLE)
            in_flight_count = sum(1 for msg in messages if msg.status == MessageStatus.IN_FLIGHT)
            
            queue_file = self._get_queue_file(queue_name)
            file_size = queue_file.stat().st_size if queue_file.exists() else 0
            
            # Get creation time (earliest message timestamp or file creation)
            creation_time = datetime.now(timezone.utc)
            if messages:
                creation_time = min(msg.timestamp for msg in messages)
            elif queue_file.exists():
                creation_time = datetime.fromtimestamp(queue_file.stat().st_ctime, tz=timezone.utc)
            
            # Get last modification time
            last_modified = creation_time
            if messages:
                last_modified = max(msg.timestamp for msg in messages)
            elif queue_file.exists():
                last_modified = datetime.fromtimestamp(queue_file.stat().st_mtime, tz=timezone.utc)
            
            return QueueInfo(
                queue_name=queue_name,
                message_count=len(messages),
                available_messages=available_count,
                in_flight_messages=in_flight_count,
                queue_size_bytes=file_size,
                created_timestamp=creation_time,
                last_modified=last_modified
            )
    
    def list_queues(self) -> List[str]:
        """List all available queues"""
        queue_files = self.data_dir.glob("*.json")
        return [f.stem for f in queue_files]
    
    async def health_check(self, queue_name: Optional[str] = None) -> bool:
        """Check if the queue service is healthy"""
        try:
            # Check if data directory is accessible
            if not self.data_dir.exists():
                return False
            
            # If queue_name is provided, check if it's accessible
            if queue_name:
                async with self._get_lock(queue_name):
                    await self._load_queue(queue_name)
            
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

# Global queue service instance
queue_service = QueueService()
