# PyQueue Server

A FastAPI-based queue server that provides REST API endpoints for message queuing operations, compatible with the PyQueue client library. Features configurable storage backends for flexibility and performance.

## Features

- **RESTful API** for queue operations with comprehensive security
- **Multiple storage backends**: JSON files (lightweight) or SQLite (high performance)
- **Multiple queue support** with isolated message storage
- **SQS-like message handling** with visibility timeouts and receipt handles
- **API Key authentication** with queue-specific permissions
- **Role-based access control** (READ, WRITE, DELETE, MANAGE permissions)
- **Health check endpoints** for monitoring
- **CORS support** for web applications
- **Docker support** for easy deployment

## Storage Backends

PyQueue Server supports two storage backends that can be configured without code changes:

### JSON Storage (Default)
- **Use case**: Development, small deployments, simple setups
- **Features**: Human-readable files, easy debugging, minimal dependencies
- **Performance**: Good for < 10,000 messages per queue
- **File location**: `./data/*.json` (one file per queue)

### SQLite Storage
- **Use case**: Production, high-performance, concurrent access
- **Features**: ACID transactions, better concurrency, optimized queries
- **Performance**: Excellent for > 10,000 messages per queue
- **Database location**: `./data/pyqueue.db` (single database file)

### Switching Storage Backends

Simply change the `STORAGE_BACKEND` setting in your `.env` file:

```bash
# Use JSON storage (default)
STORAGE_BACKEND=json

# Use SQLite storage
STORAGE_BACKEND=sqlite
```

No code changes required - the server automatically uses the configured backend!

## API Endpoints

### Queue Operations
- `POST /api/v1/queues/{queue_name}/messages` - Add message to queue
- `GET /api/v1/queues/{queue_name}/messages` - Get messages from queue (non-destructive)
- `POST /api/v1/queues/{queue_name}/messages/receive` - Receive messages (SQS-style with visibility timeout)
- `DELETE /api/v1/queues/{queue_name}/messages/{receipt_handle}` - Delete message by receipt handle
- `DELETE /api/v1/queues/{queue_name}/messages/by-id/{message_id}` - Delete message by ID
- `PUT /api/v1/queues/{queue_name}/messages/by-id/{message_id}` - Update message content
- `DELETE /api/v1/queues/{queue_name}/messages` - Clear all messages from queue

### Management & Information
- `GET /api/v1/queues/{queue_name}/info` - Get queue statistics and information
- `GET /api/v1/queues/{queue_name}/health` - Health check for specific queue
- `GET /api/v1/queues` - List all accessible queues
- `GET /api/v1/health` - Global health check

### Authentication & Security
- `GET /api/v1/auth/me` - Get current API key information
- `GET /api/v1/auth/permissions/{queue_name}` - Check permissions for specific queue

**🔐 Note**: All queue operations require API key authentication via `X-API-Key` header.

## Quick Start

### Installation

1. **Clone or create the project directory**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up API keys (Required for v1.0+):**
   
   Create `config/api_keys.json` with your API keys:
   ```json
   {
     "your-api-key-here": {
       "description": "Development API Key",
       "queues": {
         "*": ["READ", "WRITE", "DELETE", "MANAGE"]
       }
     }
   }
   ```

4. **Configure storage backend (Optional):**
   
   Create `.env` file to customize settings:
   ```bash
   # Choose storage backend
   STORAGE_BACKEND=json     # or "sqlite"
   
   # Storage paths
   JSON_STORAGE_DIR=./data
   SQLITE_DB_PATH=./data/pyqueue.db
   
   # Server settings
   HOST=localhost
   PORT=8000
   DEBUG=true
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
    queue_name="my_queue",
    api_key="your-api-key-here"  # Required for authentication
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
    queue_name="my_queue",
    api_key="your-api-key-here"  # Required for authentication
)    queue_type="remote",
    server_url="http://localhost:8000",
    queue_name="my_queue",
    api_key="your-api-key-here"  # Required for authentication
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

### Environment Variables

Create a `.env` file to configure PyQueue Server:

```bash
# ===== STORAGE CONFIGURATION =====
# Choose your storage backend
STORAGE_BACKEND=json          # "json" or "sqlite"

# JSON storage settings (when STORAGE_BACKEND=json)
JSON_STORAGE_DIR=./data

# SQLite storage settings (when STORAGE_BACKEND=sqlite) 
SQLITE_DB_PATH=./data/pyqueue.db

# ===== SERVER CONFIGURATION =====
HOST=localhost                # Server bind address
PORT=8000                    # Server port
DEBUG=true                   # Enable debug mode
LOG_LEVEL=INFO              # Logging level (DEBUG, INFO, WARNING, ERROR)

# ===== QUEUE CONFIGURATION =====
QUEUE_DATA_DIR=./data       # Legacy compatibility
MAX_MESSAGE_SIZE=262144     # Maximum message size in bytes (256KB)
DEFAULT_VISIBILITY_TIMEOUT=30  # Default visibility timeout in seconds
MAX_RECEIVE_COUNT=10        # Maximum receive count per message

# ===== API CONFIGURATION =====
API_V1_PREFIX=/api/v1       # API endpoint prefix
```

### Storage Backend Comparison

| Feature | JSON Storage | SQLite Storage |
|---------|-------------|----------------|
| **Setup** | Zero configuration | Zero configuration |
| **Performance** | Good (< 10K msgs) | Excellent (> 10K msgs) |
| **Concurrency** | File locking | Database transactions |
| **Debugging** | Human readable files | SQL queries |
| **Backup** | Copy JSON files | Single database file |
| **Dependencies** | None | aiosqlite |
| **Use Case** | Development, small scale | Production, high volume |

### API Key Configuration

Create `config/api_keys.json`:

```json
{
  "dev-key-123": {
    "description": "Development API Key",
    "queues": {
      "*": ["READ", "WRITE", "DELETE", "MANAGE"]
    }
  },
  "prod-consumer-456": {
    "description": "Production Consumer",
    "queues": {
      "orders": ["READ", "DELETE"],
      "notifications": ["READ", "DELETE"]
    }
  },
  "prod-publisher-789": {
    "description": "Production Publisher", 
    "queues": {
      "orders": ["WRITE"],
      "notifications": ["WRITE"]
    }
  }
}
```

### Permission Levels

- **READ**: Get messages, receive messages, view queue info
- **WRITE**: Add messages, update messages
- **DELETE**: Delete individual messages
- **MANAGE**: Clear entire queues, full queue management

## Development

### Project Structure
```
pyqueue-server/
├── main.py                    # FastAPI application entry point
├── requirements.txt           # Python dependencies
├── Dockerfile                # Docker configuration
├── docker-compose.yml        # Docker Compose configuration
├── .env                      # Environment configuration
├── SECURITY.md               # Security documentation
├── test_server.py            # Server functionality tests
├── test_security.py          # Security system tests
├── test_storage_backends.py  # Storage backend tests
├── config/
│   └── api_keys.json         # API key configuration
├── data/                     # Queue data storage
│   ├── *.json               # JSON queue files (if using JSON backend)
│   └── pyqueue.db           # SQLite database (if using SQLite backend)
└── app/
    ├── core/
    │   ├── config.py         # Application configuration
    │   ├── security.py       # Authentication & authorization
    │   └── storage/          # Storage abstraction layer
    │       ├── __init__.py   # Storage factory
    │       ├── base.py       # Storage interface
    │       ├── json_storage.py   # JSON file storage
    │       └── sqlite_storage.py # SQLite storage
    ├── models/
    │   └── queue.py          # Pydantic data models
    ├── services/
    │   └── queue_service.py  # Queue management logic
    └── api/
        └── routes.py         # REST API endpoints
```

### Running in Development Mode

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Testing the Server

Run the comprehensive test suite:

```bash
# Test server functionality
python test_server.py

# Test security system
python test_security.py

# Test both storage backends
python test_storage_backends.py
```

### Testing Individual Endpoints

**Note**: All API calls require the `X-API-Key` header for authentication.

```bash
# Health check (no authentication required)
curl http://localhost:8000/health

# Add a message
curl -X POST http://localhost:8000/api/v1/queues/test/messages \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"message": {"content": "Hello World"}}'

# Get messages
curl -H "X-API-Key: your-api-key-here" \
  http://localhost:8000/api/v1/queues/test/messages

# Receive messages (SQS-style)
curl -X POST -H "X-API-Key: your-api-key-here" \
  "http://localhost:8000/api/v1/queues/test/messages/receive?max_messages=5&visibility_timeout=30"

# Queue info
curl -H "X-API-Key: your-api-key-here" \
  http://localhost:8000/api/v1/queues/test/info

# List accessible queues
curl -H "X-API-Key: your-api-key-here" \
  http://localhost:8000/api/v1/queues

# Check API key permissions
curl -H "X-API-Key: your-api-key-here" \
  http://localhost:8000/api/v1/auth/me
```

### Performance Testing

Test SQLite vs JSON storage performance:

```bash
# Test with JSON storage
STORAGE_BACKEND=json python test_storage_backends.py

# Test with SQLite storage  
STORAGE_BACKEND=sqlite python test_storage_backends.py
```
curl -H "X-API-Key: your-api-key-here" \
  http://localhost:8000/api/v1/queues/test/messages

# Queue info
curl -H "X-API-Key: your-api-key-here" \
  http://localhost:8000/api/v1/queues/test/info
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test suites
python test_server.py        # Core functionality
python test_security.py      # Authentication & authorization  
python test_storage_backends.py  # Storage backend comparison
```

## Storage Backend Migration

### From JSON to SQLite

1. **Backup your data:**
   ```bash
   cp -r ./data ./data_backup
   ```

2. **Update configuration:**
   ```bash
   # In .env file
   STORAGE_BACKEND=sqlite
   ```

3. **Restart the server:**
   ```bash
   python main.py
   ```

4. **The SQLite database will be created automatically**

### From SQLite to JSON

1. **Update configuration:**
   ```bash
   # In .env file  
   STORAGE_BACKEND=json
   ```

2. **Restart the server:**
   ```bash
   python main.py
   ```

3. **Existing JSON files will be used automatically**

**Note**: Data migration between backends is not automatic. Each backend maintains its own data store.

## Docker Support

### Using Docker Compose (Recommended)

```bash
# Build and run with Docker Compose
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Manual Docker Usage

```bash
# Build image
docker build -t pyqueue-server .

# Run with JSON storage
docker run -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config:/app/config \
  pyqueue-server

# Run with SQLite storage
docker run -p 8000:8000 \
  -e STORAGE_BACKEND=sqlite \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config:/app/config \
  pyqueue-server
```

### Docker Environment Variables

```yaml
# docker-compose.yml
version: '3.8'
services:
  pyqueue-server:
    build: .
    ports:
      - "8000:8000"
    environment:
      - STORAGE_BACKEND=sqlite
      - HOST=0.0.0.0
      - PORT=8000
      - DEBUG=false
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/app/data
      - ./config:/app/config
```

## Monitoring & Production

### Health Checks

```bash
# Global health check
curl http://localhost:8000/health

# Queue-specific health check
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/queues/your-queue/health
```

### Metrics & Monitoring

Monitor these endpoints for production deployment:
- `GET /health` - Overall service health
- `GET /api/v1/queues` - Queue statistics
- `GET /api/v1/queues/{name}/info` - Individual queue metrics

### Production Recommendations

1. **Use SQLite storage** for better performance
2. **Set up proper API keys** with specific permissions
3. **Configure appropriate visibility timeouts**
4. **Monitor queue depths** and processing rates
5. **Set up log aggregation** for debugging
6. **Use Docker** for consistent deployments

## What's New in v1.0

### 🚀 Major Features

- **Configurable Storage Backends**: Choose between JSON files or SQLite database
- **API Key Authentication**: Secure access with configurable API keys  
- **Role-Based Permissions**: Fine-grained access control per queue
- **Enhanced Performance**: SQLite backend for high-throughput scenarios
- **Storage Abstraction**: Switch backends without code changes

### 🔧 Technical Improvements

- **Async Storage Operations**: All storage operations are fully asynchronous
- **Better Error Handling**: Comprehensive error responses and logging
- **Health Check System**: Monitor both global and queue-specific health
- **Type Safety**: Full type hints throughout the codebase
- **Comprehensive Testing**: Test suites for functionality, security, and storage

### 📊 Performance Enhancements

- **SQLite Integration**: Database transactions for better concurrency
- **Optimized Queries**: Indexed database operations for fast lookups
- **Connection Pooling**: Efficient database connection management
- **Background Processing**: Non-blocking I/O operations

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## Support

- **Documentation**: Check the `/docs` endpoint when the server is running
- **Issues**: Report bugs and feature requests on GitHub
- **Security**: See `SECURITY.md` for security-related information
