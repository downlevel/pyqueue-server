import sqlite3
import json
import time
import uuid
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import aiosqlite
import asyncio

from .base import StorageBackend


class SQLiteStorage(StorageBackend):
    """SQLite storage backend for PyQueue with async operations"""
    
    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path
        self._ensure_directory()
    
    def _ensure_directory(self):
        """Ensure the directory for the database file exists"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    async def initialize(self) -> None:
        """Initialize SQLite database with required tables"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS queues (
                    name TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    attributes TEXT DEFAULT '{}'
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    queue_name TEXT NOT NULL,
                    message_body TEXT NOT NULL,
                    attributes TEXT DEFAULT '{}',
                    timestamp TEXT NOT NULL,
                    status TEXT DEFAULT 'available',
                    visibility_timeout_until TEXT NULL,
                    receipt_handle TEXT NULL,
                    receive_count INTEGER DEFAULT 0,
                    FOREIGN KEY (queue_name) REFERENCES queues(name)
                )
            """)
            
            # Create indexes for better performance
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_queue_status 
                ON messages(queue_name, status)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_visibility 
                ON messages(visibility_timeout_until)
            """)
            
            await db.commit()
    
    async def add_message(self, queue_name: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add message to queue"""
        async with self.lock:
            async with aiosqlite.connect(self.db_path) as db:
                # Ensure queue exists
                await self._ensure_queue_exists(db, queue_name)
                
                message_id = str(uuid.uuid4())
                timestamp = datetime.now().isoformat()
                
                # Extract message body and attributes
                message_body = message_data.get("message_body", message_data)
                attributes = message_data.get("attributes", {})
                
                await db.execute("""
                    INSERT INTO messages (
                        id, queue_name, message_body, attributes, timestamp, status
                    ) VALUES (?, ?, ?, ?, ?, 'available')
                """, (
                    message_id,
                    queue_name,
                    json.dumps(message_body),
                    json.dumps(attributes),
                    timestamp
                ))
                
                await db.commit()
                
                return {
                    "message_id": message_id,
                    "message_body": message_body,
                    "attributes": attributes,
                    "timestamp": timestamp,
                    "status": "available"
                }
    
    async def get_messages(self, queue_name: str, limit: int = 10, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """Get messages from queue (non-destructive read)"""
        if offset < 0:
            offset = 0
        async with aiosqlite.connect(self.db_path) as db:
            count_cursor = await db.execute("""
                SELECT COUNT(*)
                FROM messages
                WHERE queue_name = ?
            """, (queue_name,))
            total_row = await count_cursor.fetchone()
            total = total_row[0] if total_row else 0
            await count_cursor.close()

            cursor = await db.execute("""
                SELECT id, message_body, attributes, timestamp, status, receive_count
                FROM messages 
                WHERE queue_name = ? 
                ORDER BY timestamp ASC
                LIMIT ? OFFSET ?
            """, (queue_name, limit, offset))
            
            rows = await cursor.fetchall()
            messages = []
            
            for row in rows:
                messages.append({
                    "message_id": row[0],
                    "message_body": json.loads(row[1]),
                    "attributes": json.loads(row[2]),
                    "timestamp": row[3],
                    "status": row[4],
                    "receive_count": row[5]
                })
            
            await cursor.close()
            return messages, total
    
    async def receive_messages(self, queue_name: str, max_messages: int, visibility_timeout: int) -> List[Dict[str, Any]]:
        """Receive messages with SQS-style visibility timeout"""
        async with self.lock:
            async with aiosqlite.connect(self.db_path) as db:
                now = datetime.now().isoformat()
                
                # First, make expired messages available again
                await db.execute("""
                    UPDATE messages 
                    SET status = 'available', visibility_timeout_until = NULL, receipt_handle = NULL
                    WHERE queue_name = ? AND status = 'in_flight' 
                    AND visibility_timeout_until < ?
                """, (queue_name, now))
                
                # Get available messages
                cursor = await db.execute("""
                    SELECT id, message_body, attributes, timestamp, receive_count
                    FROM messages 
                    WHERE queue_name = ? AND status = 'available'
                    ORDER BY timestamp ASC
                    LIMIT ?
                """, (queue_name, max_messages))
                
                rows = await cursor.fetchall()
                messages = []
                
                if rows:
                    visibility_until = (datetime.now() + timedelta(seconds=visibility_timeout)).isoformat()
                    
                    for row in rows:
                        message_id = row[0]
                        receipt_handle = str(uuid.uuid4())
                        new_receive_count = row[4] + 1
                        
                        # Update message status
                        await db.execute("""
                            UPDATE messages 
                            SET status = 'in_flight', 
                                visibility_timeout_until = ?,
                                receipt_handle = ?,
                                receive_count = ?
                            WHERE id = ?
                        """, (visibility_until, receipt_handle, new_receive_count, message_id))
                        
                        messages.append({
                            "message_id": message_id,
                            "message_body": json.loads(row[1]),
                            "attributes": json.loads(row[2]),
                            "timestamp": row[3],
                            "receipt_handle": receipt_handle,
                            "receive_count": new_receive_count
                        })
                
                await db.commit()
                return messages
    
    async def delete_message(self, queue_name: str, receipt_handle: str) -> bool:
        """Delete message by receipt handle"""
        async with self.lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    DELETE FROM messages 
                    WHERE queue_name = ? AND receipt_handle = ?
                """, (queue_name, receipt_handle))
                
                await db.commit()
                return cursor.rowcount > 0
    
    async def delete_message_by_id(self, queue_name: str, message_id: str) -> bool:
        """Delete message by ID"""
        async with self.lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    DELETE FROM messages 
                    WHERE queue_name = ? AND id = ?
                """, (queue_name, message_id))
                
                await db.commit()
                return cursor.rowcount > 0
    
    async def update_message(self, queue_name: str, message_id: str, new_message_body: Dict[str, Any]) -> bool:
        """Update message data"""
        async with self.lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    UPDATE messages 
                    SET message_body = ?
                    WHERE queue_name = ? AND id = ?
                """, (json.dumps(new_message_body), queue_name, message_id))
                
                await db.commit()
                return cursor.rowcount > 0
    
    async def clear_queue(self, queue_name: str) -> int:
        """Clear all messages from queue, return count of deleted messages"""
        async with self.lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    DELETE FROM messages WHERE queue_name = ?
                """, (queue_name,))
                
                await db.commit()
                return cursor.rowcount
    
    async def get_queue_info(self, queue_name: str) -> Dict[str, Any]:
        """Get queue information and statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            # Get queue metadata
            cursor = await db.execute("""
                SELECT created_at, attributes FROM queues WHERE name = ?
            """, (queue_name,))
            
            queue_row = await cursor.fetchone()
            if not queue_row:
                return {
                    "exists": False,
                    "queue_name": queue_name
                }
            
            # Get message counts
            cursor = await db.execute("""
                SELECT 
                    COUNT(*) as total_messages,
                    COUNT(CASE WHEN status = 'available' THEN 1 END) as available_messages,
                    COUNT(CASE WHEN status = 'in_flight' THEN 1 END) as in_flight_messages
                FROM messages 
                WHERE queue_name = ?
            """, (queue_name,))
            
            counts = await cursor.fetchone()
            
            return {
                "exists": True,
                "queue_name": queue_name,
                "created_at": queue_row[0],
                "attributes": json.loads(queue_row[1]),
                "total_messages": counts[0],
                "available_messages": counts[1],
                "in_flight_messages": counts[2]
            }
    
    async def list_queues(self) -> List[str]:
        """List all available queues"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT name FROM queues ORDER BY name")
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    async def health_check(self, queue_name: Optional[str] = None) -> bool:
        """Check if the storage backend is healthy"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("SELECT 1")
                return True
        except Exception:
            return False
    
    async def _ensure_queue_exists(self, db: aiosqlite.Connection, queue_name: str):
        """Ensure a queue exists in the database"""
        cursor = await db.execute("SELECT 1 FROM queues WHERE name = ?", (queue_name,))
        if not await cursor.fetchone():
            await db.execute("""
                INSERT INTO queues (name, created_at) VALUES (?, ?)
            """, (queue_name, datetime.now().isoformat()))
