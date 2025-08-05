# PyQueue Server

A FastAPI-based queue server that provides REST API endpoints for message queuing operations, compatible with the PyQueue client library.

## Features

- **RESTful API** for queue operations
- **Multiple queue support** with isolated message storage
- **SQS-like message handling** with visibility timeouts
- **JSON-based message persistence**
- **Health check endpoints**
- **CORS support** for web applications
- **Docker support** for easy deployment

## API Endpoints

### Queue Operations
- `POST /api/v1/queues/{queue_name}/messages` - Add message to queue
- `GET /api/v1/queues/{queue_name}/messages` - Get messages from queue
- `POST /api/v1/queues/{queue_name}/messages/receive` - Receive messages (SQS-style)
- `DELETE /api/v1/queues/{queue_name}/messages/{receipt_handle}` - Delete message by receipt handle
- `DELETE /api/v1/queues/{queue_name}/messages/by-id/{message_id}` - Delete message by ID
- `PUT /api/v1/queues/{queue_name}/messages/by-id/{message_id}` - Update message
- `DELETE /api/v1/queues/{queue_name}/messages` - Clear all messages

### Management
- `GET /api/v1/queues/{queue_name}/info` - Get queue information
- `GET /api/v1/queues/{queue_name}/health` - Health check
- `GET /api/v1/queues` - List all queues

## Quick Start

### Installation

1. **Clone or create the project directory**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Running the Server

#### Option 1: Direct execution
```bash
python main.py
```

#### Option 2: Using the launcher script
```bash
# Development mode (with auto-reload)
python start_server.py

# Production mode
python start_server.py --production --host 0.0.0.0

# Custom configuration
python start_server.py --host 0.0.0.0 --port 9000 --log-level DEBUG
```

#### Option 3: Using uvicorn directly
```bash
# Development
uvicorn main:app --reload --host localhost --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Option 4: Using Docker
```bash
# Build and run with Docker Compose
docker-compose up --build

# Or build and run manually
docker build -t pyqueue-server .
docker run -p 8000:8000 pyqueue-server
```

The server will start on `http://localhost:8000`

**API Documentation:** Visit `http://localhost:8000/docs` for interactive API documentation

### Using with PyQueue Client

First, install the PyQueue client library:
```bash
pip install pyqueue_client==0.3.0
```

Then use it in your applications:

#### Producer (sending messages)
```python
from pyqueue_client import PyQueue

# Create remote queue client
queue = PyQueue(
    queue_type="remote",
    server_url="http://localhost:8000",
    queue_name="my_queue"
)

# Add a message
queue.add_message({
    "type": "user_signup",
    "user_id": "123",
    "email": "user@example.com"
})

# Get queue information
info = queue.get_queue_info()
print(f"Messages in queue: {info['message_count']}")
```

#### Consumer (processing messages)
```python
from pyqueue_client import PyQueue
import time

# Create consumer client
consumer = PyQueue(
    queue_type="remote",
    server_url="http://localhost:8000",
    queue_name="my_queue"
)

while True:
    # Receive messages (SQS-style)
    messages = consumer.receive_messages(max_messages=5, visibility_timeout=30)
    
    for message in messages:
        try:
            # Process your message
            print(f"Processing: {message['message_body']}")
            
            # Delete message after successful processing
            consumer.delete_message(message['receipt_handle'])
            
        except Exception as e:
            print(f"Error processing message: {e}")
    
    if not messages:
        time.sleep(5)  # Wait before checking again
```

## Configuration

Environment variables:
- `HOST`: Server host (default: localhost)
- `PORT`: Server port (default: 8000)
- `QUEUE_DATA_DIR`: Directory for queue data files (default: ./data)
- `LOG_LEVEL`: Logging level (default: INFO)

## Development

### Project Structure
```
pyqueue_server/
├── main.py                 # FastAPI application entry point
├── start_server.py         # Server launcher script
├── requirements.txt        # Python dependencies
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Docker Compose configuration
├── .env                   # Environment variables
├── examples/              # Usage examples
│   └── client_usage.py   # Client usage examples
└── app/
    ├── core/
    │   └── config.py      # Application configuration
    ├── models/
    │   └── queue.py       # Pydantic models
    ├── services/
    │   └── queue_service.py # Queue management logic
    └── api/
        └── routes.py      # API endpoints
```

### Running in Development Mode

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Testing the Server

Run the test script to verify functionality:
```bash
python test_server.py
```

Or test individual endpoints:
```bash
# Health check
curl http://localhost:8000/health

# Add a message
curl -X POST http://localhost:8000/api/v1/queues/test/messages \
  -H "Content-Type: application/json" \
  -d '{"message": {"content": "Hello World"}}'

# Get messages
curl http://localhost:8000/api/v1/queues/test/messages

# Queue info
curl http://localhost:8000/api/v1/queues/test/info
```

### Running Tests

```bash
python -m pytest tests/
```

## Docker Support

```bash
# Build image
docker build -t pyqueue-server .

# Run container
docker run -p 8000:8000 pyqueue-server
```

## License

MIT License
