"""
Simple test script for PyQueue Server
"""
import asyncio
import os
import httpx
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
HOST = os.getenv("HOST", "localhost")
PORT = os.getenv("PORT", "8000")
BASE_URL = f"http://{HOST}:{PORT}"

QUEUE_NAME = os.getenv("QUEUE_NAME_TEST", "test_queue")  # Development queue name
API_KEY = os.getenv("API_KEY_TEST", "pk_dev_12345")  # Development API key

async def test_server():
    """Test the PyQueue server functionality"""
    async with httpx.AsyncClient() as client:
        print("🧪 Testing PyQueue Server")
        print("=" * 50)
        
        # Headers with API key
        headers = {"X-API-Key": API_KEY}
        
        # Test health check
        print("1. Health Check...")
        response = await client.get(f"{BASE_URL}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")        # Test adding a message
        print("\n2. Adding Message...")
        message_data = {
            "message_body": {
                "content": "Hello, PyQueue!",
                "timestamp": datetime.now().isoformat(),
                "type": "test"
            }
        }
        response = await client.post(
            f"{BASE_URL}/api/v1/queues/{QUEUE_NAME}/messages",
            json=message_data,
            headers=headers
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
          # Test getting messages
        print("\n3. Getting Messages...")
        response = await client.get(f"{BASE_URL}/api/v1/queues/{QUEUE_NAME}/messages", headers=headers)
        print(f"   Status: {response.status_code}")
        messages = response.json()
        print(f"   Found {messages['count']} messages")
          # Test receiving messages (SQS-style)
        print("\n4. Receiving Messages (SQS-style)...")
        response = await client.post(
            f"{BASE_URL}/api/v1/queues/{QUEUE_NAME}/messages/receive?max_messages=5&visibility_timeout=30",
            headers=headers
        )
        print(f"   Status: {response.status_code}")
        received_messages = response.json()
        print(f"   Received {received_messages['count']} messages")
          # Test queue info
        print("\n5. Queue Information...")
        response = await client.get(f"{BASE_URL}/api/v1/queues/{QUEUE_NAME}/info", headers=headers)
        print(f"   Status: {response.status_code}")
        queue_info = response.json()
        print(f"   Queue: {queue_info['queue_name']}")
        print(f"   Total Messages: {queue_info['message_count']}")
        print(f"   Available: {queue_info['available_messages']}")
        print(f"   In Flight: {queue_info['in_flight_messages']}")
          # Test listing queues
        print("\n6. Listing All Queues...")
        response = await client.get(f"{BASE_URL}/api/v1/queues", headers=headers)
        print(f"   Status: {response.status_code}")
        queues = response.json()
        print(f"   Found {queues['count']} queues: {queues['queues']}")
        
        # Test getting a specific message by ID (if any messages exist)
        if messages['count'] > 0:
            test_message_id = messages['messages'][0]['id']
            print(f"\n7. Getting Message by ID: {test_message_id}...")
            response = await client.get(
                f"{BASE_URL}/api/v1/queues/{QUEUE_NAME}/messages/{test_message_id}",
                headers=headers
            )
            print(f"   Status: {response.status_code}")
            message_by_id = response.json()
            print(f"   Message ID: {message_by_id.get('id')}")
            print(f"   Message Body: {message_by_id.get('message_body')}")
        else:
            print("\n7. No messages available to test get_message_by_id.")

        print("\n✅ All tests completed!")
      
if __name__ == "__main__":
    asyncio.run(test_server())
