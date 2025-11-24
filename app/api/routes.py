from fastapi import APIRouter, HTTPException, Query, Path, Depends, Request
from typing import List, Optional
import logging

from app.models.queue import (
    MessageRequest, MessageResponse, MessagesResponse, 
    QueueInfo, HealthResponse, ErrorResponse
)
from app.services.queue_service import get_queue_service
from app.core.security import (
    require_queue_permission,
    QueuePermission,
    QueueAccess,
    get_api_key_config,
    verify_api_key,
    APIKeyConfig
)

logger = logging.getLogger(__name__)

# Constants
QUEUE_NAME_DESC = "Name of the queue"
MESSAGE_NOT_FOUND = "Message not found"

router = APIRouter()

@router.post("/queues/{queue_name}/messages", response_model=MessageResponse)
async def add_message(
    queue_name: str = Path(..., description=QUEUE_NAME_DESC),
    message_request: MessageRequest = ...,
    queue_access: QueueAccess = Depends(require_queue_permission(QueuePermission.WRITE))
):
    """Add a message to the specified queue - requires WRITE permission"""
    logger.info(f"POST /queues/{queue_name}/messages - API Key: {queue_access.api_key_config.key[:20]}... - Queue: {queue_name}")
    logger.info(f"Message request received: {message_request.model_dump()}")
    try:
        service = get_queue_service()
        
        # Convert string messages to dict format for storage
        message_body = message_request.message_body
        if isinstance(message_body, str):
            message_body = {"content": message_body}
        
        message_id = await service.add_message(
            queue_name=queue_name,
            message_body=message_body,
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
    limit: int = Query(10, ge=1, le=100, description="Maximum number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip"),
    queue_access: QueueAccess = Depends(require_queue_permission(QueuePermission.READ))
):
    """Get messages from the specified queue with pagination - requires READ permission"""
    try:
        service = get_queue_service()
        messages, total = await service.get_messages(queue_name, limit=limit, offset=offset)
        
        return MessagesResponse(
            messages=messages,
            count=len(messages),
            total=total,
            offset=offset,
            limit=limit,
            has_more=(offset + len(messages)) < total
        )
    except Exception as e:
        logger.error(f"Error getting messages from queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/queues/{queue_name}/messages/receive", response_model=MessagesResponse)
async def receive_messages(
    queue_name: str = Path(..., description=QUEUE_NAME_DESC),
    max_messages: int = Query(10, ge=1, le=100, description="Maximum number of messages to return"),
    visibility_timeout: int = Query(30, ge=1, le=43200, description="Visibility timeout in seconds"),
    queue_access: QueueAccess = Depends(require_queue_permission(QueuePermission.READ))
):
    """Receive messages from the queue (SQS-style with visibility timeout) - requires READ permission"""
    try:
        service = get_queue_service()
        messages = await service.receive_messages(
            queue_name=queue_name,
            max_messages=max_messages,
            visibility_timeout=visibility_timeout
        )
        
        return MessagesResponse(
            messages=messages,
            count=len(messages),
            total=len(messages),
            offset=0,
            limit=max_messages,
            has_more=len(messages) == max_messages
        )
    except Exception as e:
        logger.error(f"Error receiving messages from queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/queues/{queue_name}/messages/{receipt_handle}")
async def delete_message(
    queue_name: str = Path(..., description=QUEUE_NAME_DESC),
    receipt_handle: str = Path(..., description="Receipt handle of the message to delete"),
    queue_access: QueueAccess = Depends(require_queue_permission(QueuePermission.DELETE))
):
    """Delete a message using its receipt handle - requires DELETE permission"""
    try:
        service = get_queue_service()
        success = await service.delete_message(queue_name, receipt_handle)
        
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
    message_id: str = Path(..., description="ID of the message to delete"),
    queue_access: QueueAccess = Depends(require_queue_permission(QueuePermission.DELETE))
):
    """Delete a message by its ID - requires DELETE permission"""
    try:
        service = get_queue_service()
        success = await service.delete_message_by_id(queue_name, message_id)
        
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
    message_request: MessageRequest = ...,
    queue_access: QueueAccess = Depends(require_queue_permission(QueuePermission.WRITE))
):
    """Update a message's content - requires WRITE permission"""
    try:
        service = get_queue_service()
        
        # Convert string messages to dict format for storage
        message_body = message_request.message_body
        if isinstance(message_body, str):
            message_body = {"content": message_body}
        
        success = await service.update_message(
            queue_name=queue_name,
            message_id=message_id,
            new_message_body=message_body
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
    queue_name: str = Path(..., description=QUEUE_NAME_DESC),
    queue_access: QueueAccess = Depends(require_queue_permission(QueuePermission.MANAGE))
):
    """Clear all messages from the specified queue - requires MANAGE permission"""
    try:
        service = get_queue_service()
        await service.clear_queue(queue_name)
        return {"status": "success", "message": "Queue cleared"}
    except Exception as e:
        logger.error(f"Error clearing queue {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/queues/{queue_name}/info", response_model=QueueInfo)
async def get_queue_info(
    queue_name: str = Path(..., description=QUEUE_NAME_DESC),
    queue_access: QueueAccess = Depends(require_queue_permission(QueuePermission.READ))
):
    """Get information about the specified queue - requires READ permission"""
    try:
        service = get_queue_service()
        queue_info = await service.get_queue_info(queue_name)
        return queue_info
    except Exception as e:
        logger.error(f"Error getting queue info for {queue_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/queues/{queue_name}/health", response_model=HealthResponse)
async def queue_health_check(
    queue_name: str = Path(..., description=QUEUE_NAME_DESC),
    queue_access: QueueAccess = Depends(require_queue_permission(QueuePermission.READ))
):
    """Health check for a specific queue - requires READ permission"""
    try:
        service = get_queue_service()
        is_healthy = await service.health_check(queue_name)
        
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
async def list_queues(
    api_key_config: APIKeyConfig = Depends(get_api_key_config)
):
    """List queues accessible to the current API key"""
    try:
        accessible_queues = list(api_key_config.get_accessible_queues())
        
        # If wildcard access, list all existing queues
        if "*" in api_key_config.queues:
            service = get_queue_service()
            all_queues = await service.list_queues()
            accessible_queues = all_queues
        
        queue_infos = []
        for queue_name in accessible_queues:
            try:
                service = get_queue_service()
                info = await service.get_queue_info(queue_name)
                queue_infos.append({
                    "queue_name": queue_name,
                    "message_count": info.message_count,
                    "available_messages": info.available_messages,
                    "in_flight_messages": info.in_flight_messages,
                    "permissions": api_key_config.queues.get(queue_name, api_key_config.queues.get("*", []))
                })
            except Exception:
                # Queue might not exist yet
                queue_infos.append({
                    "queue_name": queue_name,
                    "message_count": 0,
                    "available_messages": 0,
                    "in_flight_messages": 0,
                    "permissions": api_key_config.queues.get(queue_name, api_key_config.queues.get("*", []))
                })
        
        return {
            "queues": queue_infos,
            "count": len(queue_infos),
            "api_key_description": api_key_config.description
        }
    except Exception as e:
        logger.error(f"Error listing queues: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", response_model=HealthResponse)
async def global_health_check():
    """Global health check for the queue service - no authentication required"""
    try:
        service = get_queue_service()
        is_healthy = await service.health_check()
        
        if not is_healthy:
            raise HTTPException(status_code=503, detail="Service is not healthy")
        
        return HealthResponse(status="healthy")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Global health check failed: {e}")
        raise HTTPException(status_code=503, detail="Health check failed")

# API Key management endpoints
@router.get("/auth/me")
async def get_current_user_info(
    api_key_config: APIKeyConfig = Depends(get_api_key_config)
):
    """Get information about the current API key"""
    accessible_queues = list(api_key_config.get_accessible_queues())
    
    # Count permissions per queue
    permissions_summary = {}
    for queue_name, permissions in api_key_config.queues.items():
        permissions_summary[queue_name] = {
            "permissions": permissions,
            "can_read": QueuePermission.READ.value in permissions,
            "can_write": QueuePermission.WRITE.value in permissions,
            "can_delete": QueuePermission.DELETE.value in permissions,
            "can_manage": QueuePermission.MANAGE.value in permissions
        }
    
    return {
        "description": api_key_config.description,
        "accessible_queues": accessible_queues,
        "queue_permissions": permissions_summary,
        "total_accessible_queues": len(accessible_queues)
    }

@router.get("/auth/permissions/{queue_name}")
async def check_queue_permissions(
    queue_name: str = Path(..., description="Queue name to check permissions for"),
    api_key_config: APIKeyConfig = Depends(get_api_key_config)
):
    """Check what permissions the current API key has for a specific queue"""
    from app.core.security import api_key_manager
    
    permissions = {
        "queue_name": queue_name,
        "has_access": queue_name in api_key_config.queues or "*" in api_key_config.queues,
        "can_read": api_key_manager.check_queue_access(api_key_config, queue_name, QueuePermission.READ),
        "can_write": api_key_manager.check_queue_access(api_key_config, queue_name, QueuePermission.WRITE),
        "can_delete": api_key_manager.check_queue_access(api_key_config, queue_name, QueuePermission.DELETE),
        "can_manage": api_key_manager.check_queue_access(api_key_config, queue_name, QueuePermission.MANAGE)
    }
    
    return permissions
