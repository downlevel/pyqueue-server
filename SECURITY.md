# PyQueue Server Security Guide

## Overview

PyQueue Server implements API key-based authentication with queue-specific permissions. Each API key is associated with specific queues and permission levels, providing secure multi-tenant access.

## Authentication

All API endpoints (except health checks) require authentication via the `X-API-Key` header.

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/queues
```

## Permission System

### Permission Types

- **READ**: View messages and queue information
- **WRITE**: Add and update messages
- **DELETE**: Delete individual messages
- **MANAGE**: Clear queues and access management operations

### Queue Access Patterns

1. **User-specific queues**: Each user has full access to their own queues
2. **Shared queues**: Limited access (read-only or write-only) to common queues
3. **Service accounts**: Read-only monitoring access
4. **Admin access**: Wildcard access to all queues

## API Key Configuration

### Configuration File: `config/api_keys.json`

```json
{
  "pk_user1_abc123def456": {
    "description": "User 1 - Email Service",
    "queues": {
      "user1_notifications": ["read", "write", "delete", "manage"],
      "user1_emails": ["read", "write", "delete", "manage"],
      "shared_events": ["read"]
    }
  }
}
```

### Default API Keys (Development)

| API Key | Description | Access |
|---------|-------------|---------|
| `pk_user1_abc123def456` | User 1 - Email Service | Full access to user1_* queues, read access to shared_events |
| `pk_user2_ghi789jkl012` | User 2 - Order Processing | Full access to user2_* queues, write access to shared_events |
| `pk_service_mno345pqr678` | Monitoring Service | Read-only access to user queues |
| `pk_admin_stu901vwx234` | Admin Access | Full access to all queues (*) |
| `pk_dev_12345` | Development Key | Access to test_queue and dev_queue |

## API Endpoints

### Authentication Management

#### Get Current User Information
```bash
GET /api/v1/auth/me
Headers: X-API-Key: your-api-key

Response:
{
  "description": "User 1 - Email Service",
  "accessible_queues": ["user1_notifications", "user1_emails", "shared_events"],
  "queue_permissions": {...},
  "total_accessible_queues": 3
}
```

#### Check Queue Permissions
```bash
GET /api/v1/auth/permissions/{queue_name}
Headers: X-API-Key: your-api-key

Response:
{
  "queue_name": "user1_notifications",
  "has_access": true,
  "can_read": true,
  "can_write": true,
  "can_delete": true,
  "can_manage": true
}
```

### Queue Operations (All require appropriate permissions)

#### List Accessible Queues
```bash
GET /api/v1/queues
Headers: X-API-Key: your-api-key

Response:
{
  "queues": [
    {
      "queue_name": "user1_notifications",
      "message_count": 5,
      "available_messages": 3,
      "in_flight_messages": 2,
      "permissions": ["read", "write", "delete", "manage"]
    }
  ],
  "count": 1,
  "api_key_description": "User 1 - Email Service"
}
```

#### Add Message (Requires WRITE permission)
```bash
POST /api/v1/queues/{queue_name}/messages
Headers: X-API-Key: your-api-key
Content-Type: application/json

{
  "message": {
    "content": "Hello World",
    "timestamp": "2025-08-08T10:30:00"
  }
}
```

#### Get Messages (Requires READ permission)
```bash
GET /api/v1/queues/{queue_name}/messages?max_messages=10
Headers: X-API-Key: your-api-key
```

#### Delete Message (Requires DELETE permission)
```bash
DELETE /api/v1/queues/{queue_name}/messages/{receipt_handle}
Headers: X-API-Key: your-api-key
```

#### Clear Queue (Requires MANAGE permission)
```bash
DELETE /api/v1/queues/{queue_name}/messages
Headers: X-API-Key: your-api-key
```

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Invalid API key"
}
```

### 403 Forbidden
```json
{
  "detail": "Access denied: write permission required for queue 'user2_orders'"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["header", "x-api-key"],
      "msg": "Field required"
    }
  ]
}
```

## Security Best Practices

### Production Configuration

1. **Secure Key Storage**: Store API keys in environment variables or encrypted configuration
2. **Key Rotation**: Implement regular API key rotation
3. **Audit Logging**: Log all access attempts with API key information
4. **Rate Limiting**: Add rate limiting per API key
5. **HTTPS Only**: Use HTTPS in production environments

### Environment Variables

```bash
# Alternative to config file
export PYQUEUE_API_KEYS_JSON='{"pk_prod_key": {"description": "Production Key", "queues": {...}}}'
```

### Docker Secrets

```yaml
# docker-compose.yml
version: '3.8'
services:
  pyqueue-server:
    build: .
    environment:
      - PYQUEUE_API_KEYS_JSON_FILE=/run/secrets/api_keys
    secrets:
      - api_keys

secrets:
  api_keys:
    file: ./secrets/api_keys.json
```

## Testing Security

Run the security test suite:

```bash
python test_security.py
```

This will test:
- API key authentication
- Queue-specific permissions
- Admin access patterns
- Service account restrictions
- User information endpoints

## Client Integration

### Python Client Example

```python
import httpx

class PyQueueClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key}
    
    async def add_message(self, queue_name: str, message: dict):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/queues/{queue_name}/messages",
                json={"message": message},
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

# Usage
client = PyQueueClient("http://localhost:8000", "pk_user1_abc123def456")
await client.add_message("user1_notifications", {"content": "Hello"})
```


## Troubleshooting

### Common Issues

1. **422 Validation Error**: Missing `X-API-Key` header
2. **401 Unauthorized**: Invalid or expired API key
3. **403 Forbidden**: API key lacks required permission for the queue
4. **500 Internal Error**: Check server logs for configuration issues