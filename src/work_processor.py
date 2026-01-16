import asyncio
import json
import math
import random
import time
from typing import Dict, Any
from datetime import datetime


class WorkProcessor:
    """
    Shared business logic for both sync and async endpoints.
    Simulates CPU-intensive work with deterministic results.
    """
    
    @staticmethod
    def process_work(data: Dict[str, Any], complexity: int = 1) -> Dict[str, Any]:
        """
        Performs deterministic work based on input data and complexity.
        
        Args:
            data: Input data dictionary
            complexity: Work complexity level (1-10), affects processing time
            
        Returns:
            Dictionary containing processed results
        """
        start_time = time.perf_counter()
        
        # Simulate work based on complexity
        work_duration = complexity * 0.1  # Base duration in seconds
        
        # Deterministic computation based on input data
        input_hash = hash(json.dumps(data, sort_keys=True))
        
        # Simulate CPU work with mathematical operations
        result_value = 0
        iterations = complexity * 1000
        
        for i in range(iterations):
            # Deterministic but computationally expensive operations
            result_value += math.sin(input_hash + i) * math.cos(i)
            result_value = math.sqrt(abs(result_value)) if result_value != 0 else 1
            
            # Add some actual delay to simulate real work
            if i % 100 == 0:
                time.sleep(0.001)  # 1ms delay every 100 iterations
        
        # Generate deterministic but complex result
        processed_result = {
            "original_data": data,
            "complexity_level": complexity,
            "computed_value": round(result_value, 6),
            "data_checksum": abs(input_hash),
            "processing_metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "iterations_performed": iterations,
                "deterministic_hash": abs(hash(str(result_value))) % 1000000
            }
        }
        
        end_time = time.perf_counter()
        processing_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        return {
            "result": processed_result,
            "processing_time_ms": processing_time
        }
    
    @staticmethod
    async def process_work_async(data: Dict[str, Any], complexity: int = 1) -> Dict[str, Any]:
        """
        Async version of work processing for non-blocking execution.
        
        Args:
            data: Input data dictionary
            complexity: Work complexity level (1-10)
            
        Returns:
            Dictionary containing processed results
        """
        start_time = time.perf_counter()
        
        # Simulate work based on complexity
        work_duration = complexity * 0.1
        
        # Deterministic computation based on input data
        input_hash = hash(json.dumps(data, sort_keys=True))
        
        # Simulate async CPU work with mathematical operations
        result_value = 0
        iterations = complexity * 1000
        
        for i in range(iterations):
            # Deterministic but computationally expensive operations
            result_value += math.sin(input_hash + i) * math.cos(i)
            result_value = math.sqrt(abs(result_value)) if result_value != 0 else 1
            
            # Yield control to event loop periodically
            if i % 50 == 0:
                await asyncio.sleep(0.001)  # Non-blocking delay
        
        # Generate deterministic but complex result
        processed_result = {
            "original_data": data,
            "complexity_level": complexity,
            "computed_value": round(result_value, 6),
            "data_checksum": abs(input_hash),
            "processing_metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "iterations_performed": iterations,
                "deterministic_hash": abs(hash(str(result_value))) % 1000000
            }
        }
        
        end_time = time.perf_counter()
        processing_time = (end_time - start_time) * 1000
        
        return {
            "result": processed_result,
            "processing_time_ms": processing_time
        }
    
    @staticmethod
    def validate_input(data: Dict[str, Any]) -> bool:
        """
        Enhanced input validation for security and resource protection.
        
        Args:
            data: Input data to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(data, dict):
            return False
        
        # Must have at least one key
        if len(data) == 0:
            return False
        
        # Check for reasonable data size (prevent abuse)
        try:
            data_str = json.dumps(data)
        except (TypeError, ValueError):
            return False
            
        if len(data_str) > 10000:  # 10KB limit
            return False
        
        # Prevent deeply nested objects that could cause stack overflow
        def check_depth(obj, current_depth=0, max_depth=10):
            if current_depth > max_depth:
                return False
            if isinstance(obj, dict):
                return all(check_depth(v, current_depth + 1, max_depth) for v in obj.values())
            elif isinstance(obj, list):
                return all(check_depth(item, current_depth + 1, max_depth) for item in obj)
            return True
        
        if not check_depth(data):
            return False
        
        # Check for suspicious patterns
        data_str_lower = data_str.lower()
        suspicious_patterns = ['<script', 'javascript:', 'eval(', 'exec(']
        if any(pattern in data_str_lower for pattern in suspicious_patterns):
            return False
        
        return True