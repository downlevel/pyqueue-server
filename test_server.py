"""
Simple test script for PyQueue Server
"""
import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
QUEUE_NAME = "test_queue"

async def test_server():
    """Test the PyQueue server functionality"""
    async with httpx.AsyncClient() as client:
        print("🧪 Testing PyQueue Server")
        print("=" * 50)
        
        # Test health check
        print("1. Health Check...")
        response = await client.get(f"{BASE_URL}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
          # Test adding a message
        print("\n2. Adding Message...")
        message_data = {
            "message": {
                "content": "Hello, PyQueue!",
                "timestamp": datetime.now().isoformat(),
                "type": "test"
            }
        }
        response = await client.post(
            f"{BASE_URL}/api/v1/queues/{QUEUE_NAME}/messages",
            json=message_data
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        
        # Test getting messages
        print("\n3. Getting Messages...")
        response = await client.get(f"{BASE_URL}/api/v1/queues/{QUEUE_NAME}/messages")
        print(f"   Status: {response.status_code}")
        messages = response.json()
        print(f"   Found {messages['count']} messages")
        
        # Test receiving messages (SQS-style)
        print("\n4. Receiving Messages (SQS-style)...")
        response = await client.post(
            f"{BASE_URL}/api/v1/queues/{QUEUE_NAME}/messages/receive?max_messages=5&visibility_timeout=30"
        )
        print(f"   Status: {response.status_code}")
        received_messages = response.json()
        print(f"   Received {received_messages['count']} messages")
        
        # Test queue info
        print("\n5. Queue Information...")
        response = await client.get(f"{BASE_URL}/api/v1/queues/{QUEUE_NAME}/info")
        print(f"   Status: {response.status_code}")
        queue_info = response.json()
        print(f"   Queue: {queue_info['queue_name']}")
        print(f"   Total Messages: {queue_info['message_count']}")
        print(f"   Available: {queue_info['available_messages']}")
        print(f"   In Flight: {queue_info['in_flight_messages']}")
        
        # Test listing queues
        print("\n6. Listing All Queues...")
        response = await client.get(f"{BASE_URL}/api/v1/queues")
        print(f"   Status: {response.status_code}")
        queues = response.json()
        print(f"   Found {queues['count']} queues: {queues['queues']}")
        
        print("\n✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(test_server())
