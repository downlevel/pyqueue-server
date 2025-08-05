from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

class MessageStatus(str, Enum):
    """Message status enumeration"""
    AVAILABLE = "available"
    IN_FLIGHT = "in_flight"
    PROCESSED = "processed"

class QueueMessage(BaseModel):
    """Queue message model"""
    id: str = Field(..., description="Unique message identifier")
    message_body: Dict[Any, Any] = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message creation timestamp")
    status: MessageStatus = Field(default=MessageStatus.AVAILABLE, description="Message status")
    visibility_timeout: Optional[datetime] = Field(None, description="When message becomes visible again")
    receipt_handle: Optional[str] = Field(None, description="Handle for message operations")
    receive_count: int = Field(default=0, description="Number of times message has been received")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class MessageRequest(BaseModel):
    """Request model for adding messages"""
    id: Optional[str] = Field(None, description="Optional message ID")
    message: Dict[Any, Any] = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(None, description="Optional timestamp")

class MessageResponse(BaseModel):
    """Response model for message operations"""
    id: str = Field(..., description="Message ID")
    status: str = Field(..., description="Operation status")
    receipt_handle: Optional[str] = Field(None, description="Receipt handle for SQS-style operations")

class MessagesResponse(BaseModel):
    """Response model for getting multiple messages"""
    messages: List[QueueMessage] = Field(..., description="List of messages")
    count: int = Field(..., description="Number of messages returned")

class QueueInfo(BaseModel):
    """Queue information model"""
    queue_name: str = Field(..., description="Name of the queue")
    message_count: int = Field(..., description="Total number of messages")
    available_messages: int = Field(..., description="Number of available messages")
    in_flight_messages: int = Field(..., description="Number of in-flight messages")
    queue_size_bytes: int = Field(..., description="Approximate queue size in bytes")
    created_timestamp: datetime = Field(..., description="Queue creation time")
    last_modified: datetime = Field(..., description="Last modification time")

class HealthResponse(BaseModel):
    """Health check response model"""
    status: str = Field(..., description="Health status")
    queue_name: Optional[str] = Field(None, description="Queue name if applicable")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")

class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
