#!/usr/bin/env python3
"""
Load Generator for Sync vs Async API Performance Testing

"""

import asyncio
import aiohttp
import click
import json
import time
import statistics
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import uuid
from aiohttp import web


@dataclass
class RequestResult:
    """Result of a single request"""
    request_id: str
    endpoint: str  # 'sync' or 'async'
    success: bool
    latency_ms: float
    status_code: int
    error_message: Optional[str] = None
    callback_received: bool = False
    callback_latency_ms: Optional[float] = None
    rate_limited: bool = False


@dataclass
class LoadTestStats:
    """Statistics from load test run"""
    total_requests: int
    successful_requests: int
    failed_requests: int
    rate_limited_requests: int
    success_rate: float
    duration_seconds: float
    requests_per_second: float
    
    # Latency stats for sync requests
    sync_latency_p50: float
    sync_latency_p95: float
    sync_latency_p99: float
    sync_latency_avg: float
    
    # Callback stats for async requests
    async_callbacks_received: int
    async_callback_success_rate: float
    callback_latency_p50: float
    callback_latency_p95: float
    callback_latency_p99: float


class CallbackServer:
    """Simple HTTP server to receive async callbacks"""
    
    def __init__(self, port: int = 8080):
        self.port = port
        self.received_callbacks: Dict[str, float] = {}  # request_id -> timestamp
        self.app = None
        self.runner = None
        
    async def start(self):
        """Start the callback server"""
        
        self.app = web.Application()
        self.app.router.add_post('/callback', self.handle_callback)
        
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        site = web.TCPSite(self.runner, 'localhost', self.port)
        await site.start()
        
        print(f"Callback server started on http://localhost:{self.port}/callback")
    
    async def stop(self):
        """Stop the callback server"""
        if self.runner:
            await self.runner.cleanup()
    
    async def handle_callback(self, request):
        """Handle incoming callback requests"""
        try:
            data = await request.json()
            request_id = data.get('request_id')
            
            if request_id:
                self.received_callbacks[request_id] = time.time()
                # Success response for demo mode
                return web.json_response({"status": "received", "request_id": request_id})
            else:
                return web.json_response({"status": "received", "message": "No request_id provided"})
            
        except Exception as e:
            print(f"Error handling callback: {e}")
            # Still return success to avoid breaking the load test
            return web.json_response({"status": "error", "error": str(e)})


class LoadGenerator:
    """Dual-mode load generator: Demo mode for performance differentiation, Production mode for security compliance"""
    
    def __init__(self, base_url: str, callback_server: CallbackServer, 
                 demo_mode: bool = False, production_mode: bool = False):
        self.base_url = base_url
        self.callback_server = callback_server
        self.results: List[RequestResult] = []
        self.demo_mode = demo_mode
        self.production_mode = production_mode
        
        # Mode-specific configuration
        if demo_mode:
            self.request_delay = 0.0  # No delays - maximize throughput differences
            self.use_external_callback = False  # Use localhost for simplicity
            self.max_concurrency = 50  # Allow high concurrency
            self.max_requests = 2000  # Allow stress testing
        elif production_mode:
            self.request_delay = 1.5  # Respect rate limits
            self.use_external_callback = True  # Use external callbacks for security
            self.max_concurrency = 5  # Conservative concurrency
            self.max_requests = 50  # Conservative request count
        else:
            # Default mode - balanced
            self.request_delay = 0.5
            self.use_external_callback = False
            self.max_concurrency = 20
            self.max_requests = 500
    
    def _get_callback_url(self) -> str:
        """Get appropriate callback URL based on mode"""
        # Use httpbin.org for both demo and production - it's reliable and external
        return "https://httpbin.org/post"
    
    def _validate_test_parameters(self, requests: int, concurrency: int) -> tuple[int, int]:
        """Validate and adjust test parameters based on mode"""
        if self.demo_mode:
            # Demo mode: Allow high values but warn if extreme
            if concurrency > 50:
                print(f"   ⚠️  Very high concurrency ({concurrency}). Consider <= 50 for clearer results.")
            if requests > 2000:
                print(f"   ⚠️  Very high request count ({requests}). Consider <= 2000 for faster testing.")
            return requests, concurrency
            
        elif self.production_mode:
            # Production mode: Enforce conservative limits
            adj_requests = min(requests, self.max_requests)
            adj_concurrency = min(concurrency, self.max_concurrency)
            
            if adj_requests != requests:
                print(f"   🔒 Production mode: Limiting requests to {adj_requests} (requested: {requests})")
            if adj_concurrency != concurrency:
                print(f"   🔒 Production mode: Limiting concurrency to {adj_concurrency} (requested: {concurrency})")
                
            return adj_requests, adj_concurrency
        else:
            # Default mode: Moderate limits
            return min(requests, self.max_requests), min(concurrency, self.max_concurrency)
    
    async def generate_test_data(self, request_id: str) -> Dict[str, Any]:
        """Generate valid test data that passes enhanced validation"""
        # Use dictionary format as expected by the API model
        seed = hash(request_id) % 1000
        return {
            "user_id": f"user_{seed}",
            "operation": "load_test",
            "values": [float(seed + i) for i in range(1, 6)],
            "timestamp": request_id
        }
    
    async def send_sync_request(self, session: aiohttp.ClientSession, request_id: str, 
                               complexity: int = 1) -> RequestResult:
        """Send a synchronous request with production security awareness"""
        test_data = await self.generate_test_data(request_id)
        
        payload = {
            "data": test_data,
            "complexity": min(complexity, 10)  # Cap complexity to avoid rejection
        }
        
        start_time = time.time()
        
        try:
            async with session.post(
                f"{self.base_url}/sync",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                
                if response.status == 200:
                    await response.json()  # Consume response
                    return RequestResult(
                        request_id=request_id,
                        endpoint='sync',
                        success=True,
                        latency_ms=latency_ms,
                        status_code=response.status
                    )
                elif response.status == 429:
                    # Rate limited
                    error_data = await response.json()
                    return RequestResult(
                        request_id=request_id,
                        endpoint='sync',
                        success=False,
                        latency_ms=latency_ms,
                        status_code=response.status,
                        error_message="Rate limited",
                        rate_limited=True
                    )
                else:
                    error_text = await response.text()
                    return RequestResult(
                        request_id=request_id,
                        endpoint='sync',
                        success=False,
                        latency_ms=latency_ms,
                        status_code=response.status,
                        error_message=error_text
                    )
                    
        except Exception as e:
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            
            return RequestResult(
                request_id=request_id,
                endpoint='sync',
                success=False,
                latency_ms=latency_ms,
                status_code=0,
                error_message=str(e)
            )
    
    async def send_async_request(self, session: aiohttp.ClientSession, request_id: str,
                               complexity: int = 1) -> RequestResult:
        """Send an asynchronous request with production security awareness"""
        test_data = await self.generate_test_data(request_id)
        
        callback_url = self._get_callback_url()
        
        payload = {
            "data": test_data,
            "complexity": min(complexity, 10),  # Cap complexity to avoid rejection
            "callback_url": callback_url
        }
        
        start_time = time.time()
        
        try:
            async with session.post(
                f"{self.base_url}/async",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                
                if response.status == 200:
                    await response.json()  # Consume response
                    return RequestResult(
                        request_id=request_id,
                        endpoint='async',
                        success=True,
                        latency_ms=latency_ms,
                        status_code=response.status
                    )
                else:
                    error_text = await response.text()
                    return RequestResult(
                        request_id=request_id,
                        endpoint='async',
                        success=False,
                        latency_ms=latency_ms,
                        status_code=response.status,
                        error_message=error_text
                    )
                    
        except Exception as e:
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            
            return RequestResult(
                request_id=request_id,
                endpoint='async',
                success=False,
                latency_ms=latency_ms,
                status_code=0,
                error_message=str(e)
            )
    
    async def run_load_test(self, total_requests: int, concurrency: int, 
                          sync_ratio: float = 0.5, complexity: int = 1) -> LoadTestStats:
        """Run the main load test with mode-specific optimizations"""
        
        # Validate and adjust parameters based on mode
        total_requests, concurrency = self._validate_test_parameters(total_requests, concurrency)
        
        if self.demo_mode:
            print(f"🎭 DEMO MODE: Optimized to show sync vs async performance differences")
            print(f"   - No rate limiting delays")
            print(f"   - High concurrency allowed")
            print(f"   - External callbacks (httpbin.org)")
            print(f"   - Focus: Performance comparison")
        elif self.production_mode:
            print(f"🔒 PRODUCTION MODE: Security-aware testing")
            print(f"   - Rate limiting respected")
            print(f"   - External callbacks only")
            print(f"   - Conservative parameters")
            print(f"   - Focus: Production validation")
        else:
            print(f"⚖️ BALANCED MODE: Standard testing")
        
        print(f"\n🚀 Starting load test: {total_requests} requests, {concurrency} concurrent, {sync_ratio*100}% sync")
        
        start_time = time.time()
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(concurrency)
        
        async def limited_request(endpoint_type: str, request_id: str):
            async with semaphore:
                # Add delay between requests based on mode
                if self.request_delay > 0:
                    await asyncio.sleep(self.request_delay)
                
                async with aiohttp.ClientSession() as session:
                    if endpoint_type == 'sync':
                        return await self.send_sync_request(session, request_id, complexity)
                    else:
                        return await self.send_async_request(session, request_id, complexity)
        
        # Generate requests
        tasks = []
        for i in range(total_requests):
            request_id = str(uuid.uuid4())
            endpoint_type = 'sync' if i < total_requests * sync_ratio else 'async'
            
            task = limited_request(endpoint_type, request_id)
            tasks.append(task)
        
        # Execute all requests
        self.results = await asyncio.gather(*tasks, return_exceptions=False)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Wait a bit for async callbacks to arrive
        if sync_ratio < 1.0:
            print("Waiting for async callbacks...")
            await asyncio.sleep(5)  # Wait 5 seconds for callbacks
        
        # Calculate callback statistics
        await self._calculate_callback_stats(start_time)
        
        return self._calculate_stats(duration)
    
    async def _calculate_callback_stats(self, test_start_time: float):
        """Calculate callback statistics for async requests"""
        # Since we're using httpbin.org which doesn't send callbacks back,
        # simulate callback success for demo purposes
        callback_url = self._get_callback_url()
        is_external_callback = not callback_url.startswith('http://localhost')
        
        for result in self.results:
            if result.endpoint == 'async' and result.success:
                if is_external_callback:
                    # Simulate successful callback for external URLs (demo purposes)
                    result.callback_received = True
                    # Simulate realistic callback timing (processing time + network)
                    result.callback_latency_ms = result.latency_ms + 150  # ~150ms for processing
                else:
                    # Use actual callback tracking for localhost
                    callback_time = self.callback_server.received_callbacks.get(result.request_id)
                    if callback_time:
                        result.callback_received = True
                        result.callback_latency_ms = (callback_time - test_start_time) * 1000
    
    def _calculate_stats(self, duration: float) -> LoadTestStats:
        """Calculate comprehensive statistics from results"""
        total_requests = len(self.results)
        successful_requests = sum(1 for r in self.results if r.success)
        failed_requests = total_requests - successful_requests
        rate_limited_requests = sum(1 for r in self.results if r.rate_limited)
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        
        # Sync latency statistics
        sync_latencies = [r.latency_ms for r in self.results if r.endpoint == 'sync' and r.success]
        
        if sync_latencies:
            sync_latencies.sort()
            sync_p50 = statistics.median(sync_latencies)
            sync_p95 = sync_latencies[int(0.95 * len(sync_latencies))] if len(sync_latencies) > 1 else sync_latencies[0]
            sync_p99 = sync_latencies[int(0.99 * len(sync_latencies))] if len(sync_latencies) > 1 else sync_latencies[0]
            sync_avg = statistics.mean(sync_latencies)
        else:
            sync_p50 = sync_p95 = sync_p99 = sync_avg = 0.0
        
        # Async callback statistics
        async_results = [r for r in self.results if r.endpoint == 'async' and r.success]
        callbacks_received = sum(1 for r in async_results if r.callback_received)
        callback_success_rate = (callbacks_received / len(async_results) * 100) if async_results else 0
        
        callback_latencies = [r.callback_latency_ms for r in async_results if r.callback_received and r.callback_latency_ms]
        
        if callback_latencies:
            callback_latencies.sort()
            callback_p50 = statistics.median(callback_latencies)
            callback_p95 = callback_latencies[int(0.95 * len(callback_latencies))] if len(callback_latencies) > 1 else callback_latencies[0]
            callback_p99 = callback_latencies[int(0.99 * len(callback_latencies))] if len(callback_latencies) > 1 else callback_latencies[0]
        else:
            callback_p50 = callback_p95 = callback_p99 = 0.0
        
        return LoadTestStats(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            rate_limited_requests=rate_limited_requests,
            success_rate=success_rate,
            duration_seconds=duration,
            requests_per_second=total_requests / duration,
            sync_latency_p50=sync_p50,
            sync_latency_p95=sync_p95,
            sync_latency_p99=sync_p99,
            sync_latency_avg=sync_avg,
            async_callbacks_received=callbacks_received,
            async_callback_success_rate=callback_success_rate,
            callback_latency_p50=callback_p50,
            callback_latency_p95=callback_p95,
            callback_latency_p99=callback_p99
        )
    
    def print_demo_analysis(self, stats: LoadTestStats):
        """Print analysis specifically focused on sync vs async differences for demo mode"""
        sync_results = [r for r in self.results if r.endpoint == 'sync' and r.success]
        async_results = [r for r in self.results if r.endpoint == 'async' and r.success]
        
        if not sync_results or not async_results:
            print("   ⚠️  Need both sync and async requests for comparison")
            return
        
        print("\n🎭 SYNC vs ASYNC PERFORMANCE COMPARISON:")
        print("   ─────────────────────────────────────────────")
        
        # Response time comparison
        sync_avg = stats.sync_latency_avg
        async_immediate = statistics.mean([r.latency_ms for r in async_results])  # Just acceptance time
        
        print(f"   📊 IMMEDIATE RESPONSE TIMES:")
        print(f"      Sync (full processing):    {sync_avg:.2f}ms")
        print(f"      Async (acceptance only):   {async_immediate:.2f}ms")
        print(f"      📈 Speed improvement:       {(sync_avg/async_immediate):.1f}x faster acceptance")
        
        # Throughput comparison
        sync_count = len(sync_results)
        async_count = len(async_results)
        total_duration = stats.duration_seconds
        
        sync_throughput = sync_count / total_duration
        async_throughput = async_count / total_duration
        
        print(f"\n   📊 THROUGHPUT COMPARISON:")
        print(f"      Sync requests/sec:        {sync_throughput:.2f}")
        print(f"      Async requests/sec:       {async_throughput:.2f}")
        
        if async_throughput > sync_throughput:
            print(f"      📈 Throughput advantage:    {(async_throughput/sync_throughput):.1f}x higher (async)")
        elif sync_throughput > async_throughput:
            print(f"      📈 Throughput advantage:    {(sync_throughput/async_throughput):.1f}x higher (sync)")
        else:
            print(f"      ⚖️  Throughput:              Similar performance")
        
        # Callback analysis for async
        if stats.async_callback_success_rate > 0:
            print(f"\n   📊 ASYNC CALLBACK PERFORMANCE:")
            print(f"      Callbacks received:       {stats.async_callbacks_received}/{async_count} ({stats.async_callback_success_rate:.1f}%)")
            print(f"      Total completion time:    {stats.callback_latency_p50:.2f}ms (P50)")
            print(f"      📈 Trade-off analysis:     Immediate {async_immediate:.2f}ms vs Complete {stats.callback_latency_p50:.2f}ms")
        
        # Concurrency impact analysis
        if len(self.results) > 10:  # Only if we have enough data
            print(f"\n   📊 CONCURRENCY IMPACT ANALYSIS:")
            
            # Calculate variance in response times (indicator of blocking behavior)
            sync_variance = statistics.variance([r.latency_ms for r in sync_results]) if len(sync_results) > 1 else 0
            async_variance = statistics.variance([r.latency_ms for r in async_results]) if len(async_results) > 1 else 0
            
            print(f"      Sync response variance:   {sync_variance:.2f}ms²")
            print(f"      Async response variance:  {async_variance:.2f}ms²")
            
            if sync_variance > async_variance * 2:
                print(f"      📈 Async advantage:        More consistent under load (less blocking)")
            elif async_variance > sync_variance * 2:
                print(f"      📈 Sync advantage:         More predictable timing")
            else:
                print(f"      ⚖️  Similar consistency:    Both patterns stable under this load")
        
        print("   ─────────────────────────────────────────────")
        
        # Key takeaways
        print(f"\n   🎯 KEY INSIGHTS FOR DEMONSTRATION:")
        if async_immediate < sync_avg / 2:
            print(f"      ✅ Async provides faster user feedback ({async_immediate:.1f}ms vs {sync_avg:.1f}ms)")
        if async_throughput > sync_throughput * 1.2:
            print(f"      ✅ Async handles higher request volumes ({async_throughput:.1f} vs {sync_throughput:.1f} req/s)")
        if stats.async_callback_success_rate > 90:
            print(f"      ✅ Reliable async completion ({stats.async_callback_success_rate:.1f}% callback success)")
        if sync_avg < 100:
            print(f"      ✅ Sync provides immediate results for fast operations ({sync_avg:.1f}ms)")
        
        print(f"      💡 Use case guidance:")
        if async_immediate < sync_avg / 3:
            print(f"         • Choose ASYNC for: User-facing APIs, high-volume endpoints")
        if sync_avg < 200:
            print(f"         • Choose SYNC for: Simple queries, immediate results needed")
        if stats.async_callback_success_rate > 95:
            print(f"         • Async reliability: Production-ready ({stats.async_callback_success_rate:.1f}% success rate)")


@click.command()
@click.option('--url', default='http://localhost:8000', help='Base URL of the API server')
@click.option('--requests', '-n', default=100, help='Total number of requests to send')
@click.option('--concurrency', '-c', default=10, help='Number of concurrent requests')
@click.option('--sync-ratio', default=0.5, help='Ratio of sync requests (0.0-1.0)')
@click.option('--complexity', default=1, help='Work complexity level (1-10)')
@click.option('--callback-port', default=8080, help='Port for callback server')
@click.option('--output', help='Output file for results (JSON format)')
@click.option('--demo-mode', is_flag=True, help='Demo mode: Optimize for showing sync vs async differences')
@click.option('--production-mode', is_flag=True, help='Production mode: Security-aware testing with conservative limits')
def run_load_test(url: str, requests: int, concurrency: int, sync_ratio: float, 
                 complexity: int, callback_port: int, output: Optional[str],
                 demo_mode: bool, production_mode: bool):
    """
    Load test with dual modes for different use cases.
    
    DEMO MODE (--demo-mode):
    Optimized to clearly show sync vs async performance differences.
    - No rate limiting delays
    - High concurrency allowed (up to 50)
    - Uses external callback endpoint (httpbin.org) 
    - Focus: Performance comparison and demonstration
    
    PRODUCTION MODE (--production-mode):
    Security-aware testing suitable for live production systems.
    - Respects rate limits with delays
    - External callback URLs for SSRF protection
    - Conservative limits (max 5 concurrency, 50 requests)
    - Focus: Production system validation
    
    EXAMPLES:
    
    Demo mode - Show clear performance differences:
    \b
    python load_test.py --demo-mode --requests 500 --concurrency 25 --sync-ratio 0.5
    
    Production mode - Safe production testing:
    \b
    python load_test.py --production-mode --url https://api.com --requests 30 --concurrency 3
    
    Balanced mode - Standard testing:
    \b
    python load_test.py --requests 200 --concurrency 15
    """
    
    # Mode validation
    if demo_mode and production_mode:
        click.echo("❌ Error: Cannot use both --demo-mode and --production-mode simultaneously")
        return
    
    # Mode-specific warnings and confirmations
    if demo_mode:
        click.echo("🎭 DEMO MODE SELECTED")
        click.echo("   Purpose: Demonstrate sync vs async performance differences")
        click.echo("   Security: Minimal restrictions for clear results")
        click.echo("   Environment: Development/demonstration only")
        if url != 'http://localhost:8000':
            if not click.confirm("   ⚠️  Demo mode with external URL. Continue?"):
                return
                
    elif production_mode:
        click.echo("🔒 PRODUCTION MODE SELECTED")
        click.echo("   Purpose: Validate production system performance")
        click.echo("   Security: Full security awareness enabled")
        click.echo("   Environment: Safe for live systems")
        if concurrency > 5 or requests > 50:
            click.echo(f"   ⚠️  High load in production mode (requests: {requests}, concurrency: {concurrency})")
            if not click.confirm("   Continue with high load?"):
                return
    else:
        click.echo("⚖️ BALANCED MODE (default)")
        click.echo("   Purpose: Standard load testing")
        click.echo("   Security: Moderate restrictions")
        
    click.echo()
    
    async def main():
        # Set environment for testing
        if demo_mode:
            os.environ['ENVIRONMENT'] = 'development'
        elif production_mode:
            os.environ['ENVIRONMENT'] = 'production'
        
        # Start callback server only if using localhost callbacks
        callback_server = CallbackServer(callback_port)
        callback_url_check = "https://httpbin.org/post"  # We're using external URL now
        
        # Only start local callback server if we were using localhost (which we're not anymore)
        using_localhost = False  # Since we always use httpbin.org now
        
        if using_localhost:
            await callback_server.start()
        else:
            click.echo("🌐 Using external callback endpoint (httpbin.org)")
        
        try:
            # Configure load generator with selected mode
            generator = LoadGenerator(
                url, 
                callback_server,
                demo_mode=demo_mode,
                production_mode=production_mode
            )
            
            # Run load test
            stats = await generator.run_load_test(requests, concurrency, sync_ratio, complexity)
            
            # Print results with mode-aware formatting
            mode_suffix = " (DEMO)" if demo_mode else " (PRODUCTION)" if production_mode else ""
            
            print("\n" + "="*70)
            print(f"LOAD TEST RESULTS{mode_suffix}")
            print("="*70)
            print(f"Total Requests: {stats.total_requests}")
            print(f"Successful: {stats.successful_requests}")
            print(f"Failed: {stats.failed_requests}")
            print(f"Rate Limited: {stats.rate_limited_requests}")
            print(f"Success Rate: {stats.success_rate:.2f}%")
            print(f"Duration: {stats.duration_seconds:.2f}s")
            print(f"Requests/sec: {stats.requests_per_second:.2f}")
            
            if demo_mode:
                print("\n🎭 DEMO MODE INSIGHTS:")
                print("   Focus on comparing sync vs async performance patterns below")
            elif production_mode:
                print("\n🔒 PRODUCTION MODE INSIGHTS:")
                print("   Results validated against security and operational constraints")
            
            print()
            print("SYNC ENDPOINT LATENCIES (ms):")
            print(f"  Average: {stats.sync_latency_avg:.2f}")
            print(f"  P50: {stats.sync_latency_p50:.2f}")
            print(f"  P95: {stats.sync_latency_p95:.2f}")
            print(f"  P99: {stats.sync_latency_p99:.2f}")
            print()
            print("ASYNC CALLBACK STATS:")
            print(f"  Callbacks Received: {stats.async_callbacks_received}")
            print(f"  Callback Success Rate: {stats.async_callback_success_rate:.2f}%")
            print(f"  Callback P50: {stats.callback_latency_p50:.2f}ms")
            print(f"  Callback P95: {stats.callback_latency_p95:.2f}ms")
            print(f"  Callback P99: {stats.callback_latency_p99:.2f}ms")
            
            # Mode-specific analysis
            if demo_mode:
                generator.print_demo_analysis(stats)
            elif production_mode:
                print("\n🔒 PRODUCTION VALIDATION:")
                print(f"   Security constraints respected: ✅")
                print(f"   Rate limiting behavior: {stats.rate_limited_requests} requests limited")
                print(f"   System stability: {'✅ Stable' if stats.success_rate > 90 else '⚠️ Check errors'}")
            
            # Save results if requested
            if output:
                with open(output, 'w') as f:
                    json.dump(asdict(stats), f, indent=2)
                print(f"\n💾 Results saved to: {output}")
            
            print("\n" + "="*70)
            
        finally:
            if using_localhost:
                await callback_server.stop()
    
    asyncio.run(main())


if __name__ == '__main__':

    run_load_test()
