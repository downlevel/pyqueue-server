"""
Security test script for PyQueue Server
Tests API key authentication and authorization
"""
import asyncio
import httpx
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get host and port from environment variables
HOST = os.getenv("HOST", "localhost")
PORT = os.getenv("PORT", "8000")
BASE_URL = f"http://{HOST}:{PORT}"

# Test API keys from configuration
API_KEYS = {
    "user1": "pk_user1_abc123def456",
    "user2": "pk_user2_ghi789jkl012", 
    "service": "pk_service_mno345pqr678",
    "admin": "pk_admin_stu901vwx234",
    "dev": "pk_dev_12345",
    "invalid": "pk_invalid_key"
}

async def test_api_key_authentication():
    """Test API key authentication"""
    print("🔐 Testing API Key Authentication")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        # Test 1: No API key
        print("1. Testing without API key...")
        response = await client.get(f"{BASE_URL}/api/v1/queues")
        if response.status_code == 422:
            print("   ✅ Correctly rejected - missing API key header")
        elif response.status_code == 200:
            print(f"   ❌ Unexpected success: {response.status_code}")
        else:
            print(f"   ❓ Unexpected error: {response.status_code}")
        
        # Test 2: Invalid API key
        print("\n2. Testing with invalid API key...")
        response = await client.get(
            f"{BASE_URL}/api/v1/queues",
            headers={"X-API-Key": API_KEYS["invalid"]}
        )
        if response.status_code == 401:
            print("   ✅ Correctly rejected invalid API key")
        else:
            print(f"   ❌ Unexpected response: {response.status_code}")
        
        # Test 3: Valid API key
        print("\n3. Testing with valid API key...")
        response = await client.get(
            f"{BASE_URL}/api/v1/queues",
            headers={"X-API-Key": API_KEYS["user1"]}
        )
        if response.status_code == 200:
            print("   ✅ Successfully authenticated with valid API key")
            data = response.json()
            print(f"   📊 Accessible queues: {[q['queue_name'] for q in data['queues']]}")
        else:
            print(f"   ❌ Authentication failed: {response.status_code}")

async def test_queue_permissions():
    """Test queue-specific permissions"""
    print("\n🎯 Testing Queue Permissions")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        # Test User1 accessing their own queue
        print("1. User1 accessing own queue (user1_notifications)...")
        response = await client.post(
            f"{BASE_URL}/api/v1/queues/user1_notifications/messages",
            headers={"X-API-Key": API_KEYS["user1"]},
            json={"message_body": {"content": "Hello from User1", "timestamp": datetime.now().isoformat()}}
        )
        if response.status_code == 200:
            print("   ✅ User1 can write to own queue")
        else:
            print(f"   ❌ User1 cannot write to own queue: {response.status_code}")
        
        # Test User1 accessing User2's queue (should fail)
        print("\n2. User1 trying to access User2's queue (user2_orders)...")
        response = await client.post(
            f"{BASE_URL}/api/v1/queues/user2_orders/messages",
            headers={"X-API-Key": API_KEYS["user1"]},
            json={"message_body": {"content": "Unauthorized access attempt"}}
        )
        if response.status_code == 403:
            print("   ✅ User1 correctly denied access to User2's queue")
        else:
            print(f"   ❌ Unexpected response: {response.status_code}")
        
        # Test User2 accessing their own queue
        print("\n3. User2 accessing own queue (user2_orders)...")
        response = await client.post(
            f"{BASE_URL}/api/v1/queues/user2_orders/messages",
            headers={"X-API-Key": API_KEYS["user2"]},
            json={"message_body": {"order_id": "12345", "status": "pending"}}
        )
        if response.status_code == 200:
            print("   ✅ User2 can write to own queue")
        else:
            print(f"   ❌ User2 cannot write to own queue: {response.status_code}")
        
        # Test shared queue access
        print("\n4. Testing shared queue access...")
        # User1 should be able to read from shared_events
        response = await client.get(
            f"{BASE_URL}/api/v1/queues/shared_events/messages",
            headers={"X-API-Key": API_KEYS["user1"]}
        )
        if response.status_code == 200:
            print("   ✅ User1 can read from shared queue")
        else:
            print(f"   ❌ User1 cannot read from shared queue: {response.status_code}")
        
        # User2 should be able to write to shared_events
        response = await client.post(
            f"{BASE_URL}/api/v1/queues/shared_events/messages",
            headers={"X-API-Key": API_KEYS["user2"]},
            json={"message_body": {"event": "user_signup", "timestamp": datetime.now().isoformat()}}
        )
        if response.status_code == 200:
            print("   ✅ User2 can write to shared queue")
        else:
            print(f"   ❌ User2 cannot write to shared queue: {response.status_code}")

async def test_admin_access():
    """Test admin access with wildcard permissions"""
    print("\n👑 Testing Admin Access")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        # Admin should be able to access any queue
        test_queues = ["user1_notifications", "user2_orders", "any_random_queue"]
        
        for queue_name in test_queues:
            print(f"Admin accessing {queue_name}...")
            response = await client.post(
                f"{BASE_URL}/api/v1/queues/{queue_name}/messages",
                headers={"X-API-Key": API_KEYS["admin"]},
                json={"message_body": {"admin_message": "Admin can access any queue"}}
            )
            if response.status_code == 200:
                print(f"   ✅ Admin can write to {queue_name}")
            else:
                print(f"   ❌ Admin cannot write to {queue_name}: {response.status_code}")

async def test_service_account():
    """Test service account with read-only access"""
    print("\n🔍 Testing Service Account (Read-Only)")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        # Service account should be able to read from monitored queues
        response = await client.get(
            f"{BASE_URL}/api/v1/queues/user1_notifications/messages",
            headers={"X-API-Key": API_KEYS["service"]}
        )
        if response.status_code == 200:
            print("   ✅ Service account can read from user1_notifications")
        else:
            print(f"   ❌ Service account cannot read: {response.status_code}")
        
        # Service account should NOT be able to write to monitored queues
        response = await client.post(
            f"{BASE_URL}/api/v1/queues/user1_notifications/messages",
            headers={"X-API-Key": API_KEYS["service"]},
            json={"message_body": {"should_fail": "true"}}
        )
        if response.status_code == 403:
            print("   ✅ Service account correctly denied write access")
        else:
            print(f"   ❌ Unexpected response: {response.status_code}")

async def test_user_info_endpoints():
    """Test user information endpoints"""
    print("\n👤 Testing User Info Endpoints")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        # Test auth/me endpoint
        for user_name, api_key in [("user1", API_KEYS["user1"]), ("admin", API_KEYS["admin"])]:
            print(f"\nGetting info for {user_name}...")
            response = await client.get(
                f"{BASE_URL}/api/v1/auth/me",
                headers={"X-API-Key": api_key}
            )
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Description: {data['description']}")
                print(f"   📋 Accessible queues: {data['accessible_queues']}")
            else:
                print(f"   ❌ Failed to get user info: {response.status_code}")
        
        # Test permission check endpoint
        print(f"\nChecking User1 permissions for user2_orders...")
        response = await client.get(
            f"{BASE_URL}/api/v1/auth/permissions/user2_orders",
            headers={"X-API-Key": API_KEYS["user1"]}
        )
        if response.status_code == 200:
            data = response.json()
            print(f"   📊 Permissions: {data}")
        else:
            print(f"   ❌ Failed to check permissions: {response.status_code}")

async def test_global_health_check():
    """Test that global health check doesn't require authentication"""
    print("\n🏥 Testing Global Health Check (No Auth)")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("   ✅ Global health check works without authentication")
        else:
            print(f"   ❌ Global health check failed: {response.status_code}")
        
        response = await client.get(f"{BASE_URL}/api/v1/health")
        if response.status_code == 200:
            print("   ✅ API health check works without authentication")
        else:
            print(f"   ❌ API health check failed: {response.status_code}")

async def run_all_tests():
    """Run all security tests"""
    print("🚀 PyQueue Server Security Tests")
    print("=" * 70)
    
    try:
        await test_api_key_authentication()
        await test_queue_permissions()
        await test_admin_access()
        await test_service_account()
        await test_user_info_endpoints()
        await test_global_health_check()
        
        print("\n" + "=" * 70)
        print("🎉 Security tests completed!")
        print("💡 Check the results above to ensure all security features work correctly.")
        
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(run_all_tests())
