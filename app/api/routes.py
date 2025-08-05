from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Optional
import logging

from app.models.queue import (
    MessageRequest, MessageResponse, MessagesResponse, 
    QueueInfo, HealthResponse, ErrorResponse
)
from app.services.queue_service import queue_service

logger = logging.getLogger(__name__)

# Constants
QUEUE_NAME_DESC = "Name of the queue"
MESSAGE_NOT_FOUND = "Message not found"

router = APIRouter()

@router.post("/queues/{queue_name}/messages", response_model=MessageResponse)
async def add_message(
    queue_name: str = Path(..., description=QUEUE_NAME_DESC),
    message_request: MessageRequest = ...
):
    """Add a message to the specified queue"""
    try:
        message_id = await queue_service.add_message(
            queue_name=queue_name,
            message_body=message_request.message,
            message_id=message_request.id
        )
        
        return MessageResponse(
            id=message_id,
            status="success"
        )
    except Exception as e:
        logger.error(f"Error adding message to queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/queues/{queue_name}/messages", response_model=MessagesResponse)
async def get_messages(
    queue_name: str = Path(..., description=QUEUE_NAME_DESC),
    max_messages: int = Query(10, ge=1, le=100, description="Maximum number of messages to return")
):
    """Get messages from the specified queue"""
    try:
        messages = await queue_service.get_messages(queue_name, max_messages)
        
        return MessagesResponse(
            messages=messages,
            count=len(messages)
        )
    except Exception as e:
        logger.error(f"Error getting messages from queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/queues/{queue_name}/messages/receive", response_model=MessagesResponse)
async def receive_messages(
    queue_name: str = Path(..., description=QUEUE_NAME_DESC),
    max_messages: int = Query(10, ge=1, le=100, description="Maximum number of messages to return"),
    visibility_timeout: int = Query(30, ge=1, le=43200, description="Visibility timeout in seconds")
):
    """Receive messages from the queue (SQS-style with visibility timeout)"""
    try:
        messages = await queue_service.receive_messages(
            queue_name=queue_name,
            max_messages=max_messages,
            visibility_timeout=visibility_timeout
        )
        
        return MessagesResponse(
            messages=messages,
            count=len(messages)
        )
    except Exception as e:
        logger.error(f"Error receiving messages from queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/queues/{queue_name}/messages/{receipt_handle}")
async def delete_message(
    queue_name: str = Path(..., description=QUEUE_NAME_DESC),
    receipt_handle: str = Path(..., description="Receipt handle of the message to delete")
):
    """Delete a message using its receipt handle"""
    try:
        success = await queue_service.delete_message(queue_name, receipt_handle)
        
        if not success:
            raise HTTPException(status_code=404, detail=MESSAGE_NOT_FOUND)
        
        return {"status": "success", "message": "Message deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting message from queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/queues/{queue_name}/messages/by-id/{message_id}")
async def delete_message_by_id(
    queue_name: str = Path(..., description=QUEUE_NAME_DESC),
    message_id: str = Path(..., description="ID of the message to delete")
):
    """Delete a message by its ID"""
    try:
        success = await queue_service.delete_message_by_id(queue_name, message_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=MESSAGE_NOT_FOUND)
        
        return {"status": "success", "message": "Message deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting message from queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/queues/{queue_name}/messages/by-id/{message_id}")
async def update_message(
    queue_name: str = Path(..., description=QUEUE_NAME_DESC),
    message_id: str = Path(..., description="ID of the message to update"),
    message_request: MessageRequest = ...
):
    """Update a message's content"""
    try:
        success = await queue_service.update_message(
            queue_name=queue_name,
            message_id=message_id,
            new_message_body=message_request.message
        )
        
        if not success:
            raise HTTPException(status_code=404, detail=MESSAGE_NOT_FOUND)
        
        return {"status": "success", "message": "Message updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating message in queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/queues/{queue_name}/messages")
async def clear_queue(
    queue_name: str = Path(..., description=QUEUE_NAME_DESC)
):
    """Clear all messages from the specified queue"""
    try:
        await queue_service.clear_queue(queue_name)
        return {"status": "success", "message": "Queue cleared"}
    except Exception as e:
        logger.error(f"Error clearing queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/queues/{queue_name}/info", response_model=QueueInfo)
async def get_queue_info(
    queue_name: str = Path(..., description=QUEUE_NAME_DESC)
):
    """Get information about the specified queue"""
    try:
        queue_info = await queue_service.get_queue_info(queue_name)
        return queue_info
    except Exception as e:
        logger.error(f"Error getting queue info for {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/queues/{queue_name}/health", response_model=HealthResponse)
async def queue_health_check(
    queue_name: str = Path(..., description=QUEUE_NAME_DESC)
):
    """Health check for a specific queue"""
    try:
        is_healthy = await queue_service.health_check(queue_name)
        
        if not is_healthy:
            raise HTTPException(status_code=503, detail="Queue is not healthy")
        
        return HealthResponse(
            status="healthy",
            queue_name=queue_name
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed for queue {queue_name}: {e}")
        raise HTTPException(status_code=503, detail="Health check failed")

@router.get("/queues")
async def list_queues():
    """List all available queues"""
    try:
        queues = queue_service.list_queues()
        return {"queues": queues, "count": len(queues)}
    except Exception as e:
        logger.error(f"Error listing queues: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", response_model=HealthResponse)
async def global_health_check():
    """Global health check for the queue service"""
    try:
        is_healthy = await queue_service.health_check()
        
        if not is_healthy:
            raise HTTPException(status_code=503, detail="Service is not healthy")
        
        return HealthResponse(status="healthy")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Global health check failed: {e}")
        raise HTTPException(status_code=503, detail="Health check failed")
