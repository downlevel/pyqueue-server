import json
import os
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import aiofiles
import logging

from .base import StorageBackend

logger = logging.getLogger(__name__)


class JSONStorage(StorageBackend):
    """JSON file storage backend for PyQueue (legacy compatibility)"""
    
    def __init__(self, data_dir: str):
        super().__init__()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self._locks: Dict[str, asyncio.Lock] = {}
    
    def _get_queue_file(self, queue_name: str) -> Path:
        """Get the file path for a queue"""
        return self.data_dir / f"{queue_name}.json"
    
    def _get_lock(self, queue_name: str) -> asyncio.Lock:
        """Get or create a lock for a queue"""
        if queue_name not in self._locks:
            self._locks[queue_name] = asyncio.Lock()
        return self._locks[queue_name]
    
    async def initialize(self) -> None:
        """Initialize JSON storage (ensure directory exists)"""
        self.data_dir.mkdir(exist_ok=True)
    
    async def _load_queue(self, queue_name: str) -> List[Dict[str, Any]]:
        """Load queue from JSON file"""
        queue_file = self._get_queue_file(queue_name)
        
        if not queue_file.exists():
            return []
        
        try:
            async with aiofiles.open(queue_file, 'r') as f:
                content = await f.read()
                if not content.strip():
                    return []
                
                data = json.loads(content)
                
                # Normalize data structure for compatibility
                for item in data:
                    # Ensure required fields exist
                    if 'id' not in item:
                        item['id'] = item.get('message_id', str(uuid.uuid4()))
                    if 'message_id' not in item:
                        item['message_id'] = item['id']
                    if 'status' not in item:
                        item['status'] = 'available'
                    if 'receive_count' not in item:
                        item['receive_count'] = 0
                    if 'attributes' not in item:
                        item['attributes'] = {}
                
                return data
        except json.JSONDecodeError as e:
            logger.error(f"Error loading queue {queue_name}: {e}")
            return []
    
    async def _save_queue(self, queue_name: str, messages: List[Dict[str, Any]]):
        """Save queue to JSON file"""
        queue_file = self._get_queue_file(queue_name)
        
        try:
            # Ensure all datetime objects are serialized as ISO strings
            serializable_messages = []
            for msg in messages:
                msg_copy = msg.copy()
                for field in ['timestamp', 'visibility_timeout', 'visibility_timeout_until']:
                    if field in msg_copy and isinstance(msg_copy[field], datetime):
                        msg_copy[field] = msg_copy[field].isoformat()
                serializable_messages.append(msg_copy)
            
            async with aiofiles.open(queue_file, 'w') as f:
                await f.write(json.dumps(serializable_messages, indent=2, default=str))
        except Exception as e:
            logger.error(f"Error saving queue {queue_name}: {e}")
            raise
    
    def _generate_receipt_handle(self) -> str:
        """Generate a unique receipt handle"""
        return f"receipt_{uuid.uuid4().hex}"
    
    async def add_message(self, queue_name: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add message to queue"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            message_id = message_data.get('id') or message_data.get('message_id') or str(uuid.uuid4())
            
            # Check if message already exists
            if any(msg.get('id') == message_id or msg.get('message_id') == message_id for msg in messages):
                logger.warning(f"Message {message_id} already exists in queue {queue_name}")
                # Return existing message data
                for msg in messages:
                    if msg.get('id') == message_id or msg.get('message_id') == message_id:
                        return msg
            
            timestamp = datetime.now(timezone.utc).isoformat()
            
            new_message = {
                "id": message_id,
                "message_id": message_id,
                "message_body": message_data.get("message_body", message_data),
                "attributes": message_data.get("attributes", {}),
                "timestamp": timestamp,
                "status": "available",
                "receive_count": 0,
                "receipt_handle": None,
                "visibility_timeout_until": None
            }
            
            messages.append(new_message)
            await self._save_queue(queue_name, messages)
            
            logger.info(f"Added message {message_id} to queue {queue_name}")
            return new_message
    
    async def get_messages(self, queue_name: str, limit: int = 10, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """Get messages from queue (non-destructive read)"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            # Filter available messages
            available_messages = [
                msg for msg in messages 
                if msg.get('status') == 'available'
            ]
            
            if offset < 0:
                offset = 0
            start = min(offset, len(available_messages))
            end = start + limit if limit is not None else None
            return available_messages[start:end], len(available_messages)
    
    async def receive_messages(
        self,
        queue_name: str,
        max_messages: int,
        visibility_timeout: int,
        consumer_id: Optional[str] = None,
        remove_after_receive: bool = False,
        only_new: bool = False
    ) -> List[Dict[str, Any]]:
        """Receive messages with visibility timeout and optional consumer filtering"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            now = datetime.now(timezone.utc)
            visibility_until = (now + timedelta(seconds=visibility_timeout)).isoformat()
            received_messages = []
            delete_indices: List[int] = []
            
            # First, make expired messages available again
            for msg in messages:
                if (msg.get('status') == 'in_flight' and 
                    msg.get('visibility_timeout_until')):
                    try:
                        timeout_dt = datetime.fromisoformat(msg['visibility_timeout_until'].replace('Z', '+00:00'))
                        if timeout_dt <= now:
                            msg['status'] = 'available'
                            msg['visibility_timeout_until'] = None
                            msg['receipt_handle'] = None
                    except (ValueError, TypeError):
                        # Invalid timestamp, reset to available
                        msg['status'] = 'available'
                        msg['visibility_timeout_until'] = None
                        msg['receipt_handle'] = None
            
            # Find available messages
                for idx, msg in enumerate(messages):
                    if msg.get('status') != 'available':
                        continue
                    if len(received_messages) >= max_messages:
                        break

                    current_receive_count = msg.get('receive_count', 0)
                    if only_new and current_receive_count > 0:
                        continue

                    history = msg.get('delivery_history', [])
                    if not isinstance(history, list):
                        history = []

                    if consumer_id and consumer_id in history:
                        continue

                    if consumer_id:
                        history.append(consumer_id)
                        msg['delivery_history'] = history

                    msg['receive_count'] = current_receive_count + 1

                    if remove_after_receive:
                        msg_copy = msg.copy()
                        msg_copy['status'] = 'processed'
                        msg_copy['visibility_timeout_until'] = None
                        msg_copy['receipt_handle'] = None
                        received_messages.append(msg_copy)
                        delete_indices.append(idx)
                    else:
                        msg['status'] = 'in_flight'
                        msg['visibility_timeout_until'] = visibility_until
                        msg['receipt_handle'] = self._generate_receipt_handle()
                        received_messages.append(msg.copy())

                if delete_indices:
                    for i in sorted(delete_indices, reverse=True):
                        messages.pop(i)

                if received_messages or delete_indices:
                    await self._save_queue(queue_name, messages)
            
            return received_messages
    
    async def delete_message(self, queue_name: str, receipt_handle: str) -> bool:
        """Delete message by receipt handle"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            # Find message with matching receipt handle
            for i, msg in enumerate(messages):
                if msg.get('receipt_handle') == receipt_handle:
                    messages.pop(i)
                    await self._save_queue(queue_name, messages)
                    logger.info(f"Deleted message with receipt handle {receipt_handle} from queue {queue_name}")
                    return True
            
            return False
    
    async def delete_message_by_id(self, queue_name: str, message_id: str) -> bool:
        """Delete message by ID"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            # Find message with matching ID
            for i, msg in enumerate(messages):
                if msg.get('id') == message_id or msg.get('message_id') == message_id:
                    messages.pop(i)
                    await self._save_queue(queue_name, messages)
                    logger.info(f"Deleted message {message_id} from queue {queue_name}")
                    return True
            
            return False
    
    async def update_message(self, queue_name: str, message_id: str, new_message_body: Dict[str, Any]) -> bool:
        """Update message data"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            # Find message with matching ID
            for msg in messages:
                if msg.get('id') == message_id or msg.get('message_id') == message_id:
                    msg['message_body'] = new_message_body
                    msg['timestamp'] = datetime.now(timezone.utc).isoformat()
                    await self._save_queue(queue_name, messages)
                    logger.info(f"Updated message {message_id} in queue {queue_name}")
                    return True
            
            return False
    
    async def get_message_by_id(self, queue_name: str, message_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific message by its ID"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            # Find message with matching ID
            for msg in messages:
                if msg.get('id') == message_id or msg.get('message_id') == message_id:
                    return msg.copy()
            
            return None

    async def clear_queue(self, queue_name: str) -> int:
        """Clear all messages from queue, return count of deleted messages"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            count = len(messages)
            await self._save_queue(queue_name, [])
            logger.info(f"Cleared {count} messages from queue {queue_name}")
            return count
    
    async def get_queue_info(self, queue_name: str) -> Dict[str, Any]:
        """Get queue information and statistics"""
        async with self._get_lock(queue_name):
            messages = await self._load_queue(queue_name)
            
            available_count = sum(1 for msg in messages if msg.get('status') == 'available')
            in_flight_count = sum(1 for msg in messages if msg.get('status') == 'in_flight')
            
            queue_file = self._get_queue_file(queue_name)
            file_size = queue_file.stat().st_size if queue_file.exists() else 0
            
            # Get creation time (earliest message timestamp or file creation)
            creation_time = datetime.now(timezone.utc)
            if messages:
                timestamps = []
                for msg in messages:
                    try:
                        if isinstance(msg.get('timestamp'), str):
                            ts = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
                            timestamps.append(ts)
                    except (ValueError, TypeError):
                        continue
                if timestamps:
                    creation_time = min(timestamps)
            elif queue_file.exists():
                creation_time = datetime.fromtimestamp(queue_file.stat().st_ctime, tz=timezone.utc)
            
            # Get last modification time
            last_modified = creation_time
            if messages:
                timestamps = []
                for msg in messages:
                    try:
                        if isinstance(msg.get('timestamp'), str):
                            ts = datetime.fromisoformat(msg['timestamp'].replace('Z', '+00:00'))
                            timestamps.append(ts)
                    except (ValueError, TypeError):
                        continue
                if timestamps:
                    last_modified = max(timestamps)
            elif queue_file.exists():
                last_modified = datetime.fromtimestamp(queue_file.stat().st_mtime, tz=timezone.utc)
            
            return {
                "exists": True,
                "queue_name": queue_name,
                "total_messages": len(messages),
                "available_messages": available_count,
                "in_flight_messages": in_flight_count,
                "queue_size_bytes": file_size,
                "created_at": creation_time.isoformat(),
                "last_modified": last_modified.isoformat(),
                "attributes": {}
            }
    
    async def list_queues(self) -> List[str]:
        """List all available queues"""
        queue_files = self.data_dir.glob("*.json")
        return [f.stem for f in queue_files]
    
    async def health_check(self, queue_name: Optional[str] = None) -> bool:
        """Check if the storage backend is healthy"""
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
            logger.error(f"JSON storage health check failed: {e}")
            return False
