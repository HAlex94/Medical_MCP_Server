"""
API Caching Utility

This module provides caching functionality for API responses to reduce the number
of external API calls, avoid rate limiting, and improve response times.
"""
import os
import json
import time
import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Default cache settings
# Use /tmp for cloud environments like Render where app directories may not be writable
# Check if we're in a cloud environment first (Render sets this)
RENDER_ENV = os.environ.get("RENDER", "false").lower() == "true"

if RENDER_ENV:
    DEFAULT_CACHE_DIR = "/tmp/medical_mcp_cache"
else:
    DEFAULT_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
    
# Emergency fallback if neither location is writable
EMERGENCY_CACHE_DIR = "/tmp/emergency_medical_mcp_cache"

DEFAULT_CACHE_TTL = 7 * 24 * 60 * 60  # 7 days in seconds

# Allow disabling cache entirely
CACHE_ENABLED = os.environ.get("ENABLE_API_CACHE", "true").lower() == "true"

# Force disable caching on Render if requested
EMERGENCY_UNCACHED = RENDER_ENV or os.environ.get("EMERGENCY_UNCACHED", "false").lower() == "true"
if EMERGENCY_UNCACHED:
    logger.warning("Emergency uncached mode active - all API caching disabled")
    CACHE_ENABLED = False

# Memory cache for frequently accessed items
_memory_cache = {}


class ApiCache:
    """API Response Cache Manager"""
    
    def __init__(
        self, 
        cache_dir: Optional[str] = None, 
        ttl_seconds: Optional[int] = None,
        service_name: str = "api"
    ):
        """
        Initialize the API cache.
        
        Args:
            cache_dir: Directory to store cache files, defaults to app/cache
            ttl_seconds: Time-to-live for cache entries in seconds
            service_name: Name of the service (used for cache file naming)
        """
        self.cache_dir = cache_dir or os.environ.get("API_CACHE_DIR", DEFAULT_CACHE_DIR)
        self.ttl_seconds = ttl_seconds or int(os.environ.get("CACHE_TTL_SECONDS", str(DEFAULT_CACHE_TTL)))
        self.service_name = service_name
        
        # Try to create cache directory and test if writable
        self.cache_dir_usable = False
        if CACHE_ENABLED and not EMERGENCY_UNCACHED:
            try:
                # Ensure cache directory exists
                os.makedirs(self.cache_dir, exist_ok=True)
                # Test if we can write to it
                test_file = os.path.join(self.cache_dir, "_test_write")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                self.cache_dir_usable = True
            except (PermissionError, OSError) as e:
                # Try emergency fallback
                logger.warning(f"Cannot use primary cache directory {self.cache_dir}: {str(e)}")
                try:
                    self.cache_dir = EMERGENCY_CACHE_DIR
                    os.makedirs(self.cache_dir, exist_ok=True)
                    # Test if we can write to fallback
                    test_file = os.path.join(self.cache_dir, "_test_write")
                    with open(test_file, "w") as f:
                        f.write("test")
                    os.remove(test_file)
                    self.cache_dir_usable = True
                    logger.info(f"Using emergency cache directory: {self.cache_dir}")
                except (PermissionError, OSError) as e2:
                    logger.error(f"Cannot use emergency cache directory either: {str(e2)}")
                    logger.warning("Cache operations will be disabled due to permission issues")
        elif EMERGENCY_UNCACHED:
            logger.info("Cache creation skipped - emergency uncached mode active")
        
    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """
        Generate a unique cache key for an API request.
        
        Args:
            endpoint: API endpoint URL
            params: Query parameters
            
        Returns:
            A unique hash string for the request
        """
        # Sort params to ensure consistent keys
        sorted_params = sorted(params.items())
        param_str = json.dumps(sorted_params)
        
        # Create a unique hash
        hash_input = f"{endpoint}:{param_str}"
        return hashlib.md5(hash_input.encode('utf-8')).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> str:
        """
        Get the file path for a cache entry.
        
        Args:
            cache_key: Unique cache key
            
        Returns:
            Path to cache file
        """
        return os.path.join(self.cache_dir, f"{self.service_name}_{cache_key}.json")
    
    def get(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get a cached API response if available and not expired.
        
        Args:
            endpoint: API endpoint URL
            params: Query parameters
            
        Returns:
            Cached response or None if not found or expired
        """
        # If caching is disabled, always return None
        if not CACHE_ENABLED:
            return None
            
        cache_key = self._get_cache_key(endpoint, params)
        
        # Try memory cache first
        memory_entry = _memory_cache.get(cache_key)
        if memory_entry:
            data, timestamp = memory_entry
            if time.time() - timestamp < self.ttl_seconds:
                logger.debug(f"Cache hit (memory): {endpoint}")
                return data
        
        # Try file cache
        try:
            cache_path = self._get_cache_path(cache_key)
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, 'r') as f:
                        cache_entry = json.load(f)
                    
                    # Check expiration
                    timestamp = cache_entry.get('timestamp', 0)
                    if time.time() - timestamp < self.ttl_seconds:
                        logger.debug(f"Cache hit (disk): {endpoint}")
                        
                        # Update memory cache
                        _memory_cache[cache_key] = (cache_entry['data'], timestamp)
                        
                        return cache_entry['data']
                    else:
                        logger.debug(f"Cache expired: {endpoint}")
                except Exception as e:
                    logger.warning(f"Error reading cache file: {e}")
        except Exception as e:
            logger.warning(f"Cache access error: {e}")
        
        return None
    
    def set(self, endpoint: str, params: Dict[str, Any], data: Dict[str, Any]) -> None:
        """
        Cache an API response.
        
        Args:
            endpoint: API endpoint URL
            params: Query parameters
            data: API response data to cache
        """
        # If caching is disabled, do nothing
        if not CACHE_ENABLED:
            return
            
        cache_key = self._get_cache_key(endpoint, params)
        timestamp = time.time()
        
        # Update memory cache
        _memory_cache[cache_key] = (data, timestamp)
        
        # Update file cache - only if cache directory is usable
        if not self.cache_dir_usable:
            logger.debug(f"Skipping disk cache write - directory not usable: {self.cache_dir}")
            return
            
        try:
            # Ensure cache directory exists (might have been deleted or not created in cloud environments)
            os.makedirs(self.cache_dir, exist_ok=True)
            
            cache_path = self._get_cache_path(cache_key)
            cache_entry = {
                'timestamp': timestamp,
                'data': data,
                'endpoint': endpoint,
                'params': params
            }
            
            with open(cache_path, 'w') as f:
                json.dump(cache_entry, f)
            logger.debug(f"Cached response for: {endpoint}")
        except Exception as e:
            logger.warning(f"Cache write error (continuing without caching): {e}")
            # Just continue without caching - this ensures the API still works even if caching fails
    
    def clear(self, endpoint: Optional[str] = None, older_than_days: Optional[int] = None) -> int:
        """
        Clear cache entries.
        
        Args:
            endpoint: Optional endpoint to clear specific entries
            older_than_days: Optional age threshold in days
            
        Returns:
            Number of entries cleared
        """
        count = 0
        
        if endpoint:
            # Clear specific endpoint from memory cache
            for key in list(_memory_cache.keys()):
                if endpoint in key:
                    del _memory_cache[key]
                    count += 1
        else:
            # Clear all memory cache
            count = len(_memory_cache)
            _memory_cache.clear()
        
        # Clear disk cache
        cache_files = Path(self.cache_dir).glob(f"{self.service_name}_*.json")
        for cache_file in cache_files:
            delete = True
            
            if endpoint or older_than_days:
                try:
                    with open(cache_file, 'r') as f:
                        cache_entry = json.load(f)
                    
                    if endpoint and endpoint not in cache_entry.get('endpoint', ''):
                        delete = False
                        
                    if older_than_days:
                        age_seconds = time.time() - cache_entry.get('timestamp', 0)
                        if age_seconds < older_than_days * 24 * 60 * 60:
                            delete = False
                except Exception:
                    # If we can't read it, delete it
                    pass
            
            if delete:
                try:
                    os.remove(cache_file)
                    count += 1
                except Exception as e:
                    logger.warning(f"Error removing cache file {cache_file}: {e}")
        
        return count


# Convenience functions
def get_cache(service_name: str) -> ApiCache:
    """
    Get a cache instance for a specific service.
    
    Args:
        service_name: Name of the service
        
    Returns:
        ApiCache instance
    """
    ttl_mapping = {
        "fda": 7 * 24 * 60 * 60,      # FDA data: 7 days
        "rxnav": 30 * 24 * 60 * 60,   # RxNav data: 30 days
        "pubmed": 1 * 24 * 60 * 60,   # PubMed data: 1 day
        "evidence": 1 * 24 * 60 * 60,  # Evidence data: 1 day
    }
    
    ttl = ttl_mapping.get(service_name.lower(), DEFAULT_CACHE_TTL)
    return ApiCache(service_name=service_name, ttl_seconds=ttl)
