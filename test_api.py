#!/usr/bin/env python3
"""
Simple test script to verify the API is working correctly.
"""

import asyncio
import aiohttp
import json
from datetime import datetime


async def test_sync_endpoint():
    """Test the synchronous endpoint"""
    print("Testing /sync endpoint...")
    
    test_data = {
        "data": {
            "test": "sync_test",
            "timestamp": datetime.now().isoformat(),
            "value": 42
        },
        "complexity": 2
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post('http://localhost:8000/sync', json=test_data) as response:
            if response.status == 200:
                result = await response.json()
                print(f"✅ Sync test successful!")
                print(f"   Request ID: {result['request_id']}")
                print(f"   Processing time: {result['processing_time_ms']:.2f}ms")
                return True
            else:
                error = await response.text()
                print(f"❌ Sync test failed: {error}")
                return False


async def test_async_endpoint():
    """Test the asynchronous endpoint"""
    print("Testing /async endpoint...")
    
    # First, start a simple callback server
    from aiohttp import web
    
    received_callback = asyncio.Event()
    callback_data = {}
    
    async def callback_handler(request):
        nonlocal callback_data
        callback_data = await request.json()
        received_callback.set()
        return web.json_response({"status": "received"})
    
    app = web.Application()
    app.router.add_post('/callback', callback_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()
    
    try:
        test_data = {
            "data": {
                "test": "async_test",
                "timestamp": datetime.now().isoformat(),
                "value": 84
            },
            "complexity": 2,
            "callback_url": "https://httpbin.org/post"
        }
        
        async with aiohttp.ClientSession() as session:
            # Send async request
            async with session.post('http://localhost:8000/async', json=test_data) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ Async request accepted!")
                    print(f"   Request ID: {result['request_id']}")
                    
                    # Wait for callback
                    print("   Waiting for callback...")
                    try:
                        await asyncio.wait_for(received_callback.wait(), timeout=10.0)
                        print(f"✅ Callback received!")
                        print(f"   Callback data: {json.dumps(callback_data, indent=2)}")
                        return True
                    except asyncio.TimeoutError:
                        print(f"❌ Callback not received within timeout")
                        return False
                else:
                    error = await response.text()
                    print(f"❌ Async test failed: {error}")
                    return False
    
    finally:
        await runner.cleanup()


async def test_monitoring_endpoints():
    """Test monitoring and stats endpoints"""
    print("Testing monitoring endpoints...")
    
    async with aiohttp.ClientSession() as session:
        # Test health endpoint
        async with session.get('http://localhost:8000/healthz') as response:
            if response.status == 200:
                health = await response.json()
                print(f"✅ Health check: {health['status']}")
            else:
                print(f"❌ Health check failed")
                return False
        
        # Test stats endpoint
        async with session.get('http://localhost:8000/stats') as response:
            if response.status == 200:
                stats = await response.json()
                print(f"✅ Stats endpoint working")
                print(f"   Total requests: {stats['total_requests']}")
                print(f"   Success rate: {stats['success_rate']}%")
            else:
                print(f"❌ Stats endpoint failed")
                return False
        
        # Test requests list endpoint
        async with session.get('http://localhost:8000/requests?limit=5') as response:
            if response.status == 200:
                requests = await response.json()
                print(f"✅ Requests list endpoint working")
                print(f"   Recent requests: {len(requests)}")
            else:
                print(f"❌ Requests list endpoint failed")
                return False
    
    return True


async def main():
    """Run all tests"""
    print("Starting API tests...\n")
    
    success_count = 0
    total_tests = 3
    
    if await test_sync_endpoint():
        success_count += 1
    
    print()
    if await test_async_endpoint():
        success_count += 1
    
    print()
    if await test_monitoring_endpoints():
        success_count += 1
    
    print(f"\n{'='*50}")
    print(f"Test Results: {success_count}/{total_tests} passed")
    print(f"{'='*50}")
    
    if success_count == total_tests:
        print("🎉 All tests passed! The API is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the API server.")


if __name__ == '__main__':
    asyncio.run(main())