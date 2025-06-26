"""
API Client Utility Module

This module provides helper functions for making HTTP requests to external APIs,
handling authentication, response parsing, error handling, and caching.
"""
import logging
import json
import os
import time
import random
import asyncio
from typing import Dict, Any, Optional, Union, Tuple, List
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv
import httpx
from httpx import Response
from app.utils.api_cache import get_cache, ApiCache

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Default request settings
DEFAULT_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
DEFAULT_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
DEFAULT_RETRY_DELAY = 1.0  # Base delay in seconds for exponential backoff

def get_api_key(key_name: str) -> Optional[str]:
    """
    Get API key from environment variables.
    
    Args:
        key_name: Name of the environment variable containing the API key
        
    Returns:
        API key as string or None if not found
    """
    api_key = os.getenv(key_name)
    if api_key:
        logger.info(f"Found API key for {key_name}")
        return api_key
    else:
        logger.warning(f"No API key found for {key_name}, will attempt unauthenticated access")
        return None

async def make_request(
    url: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    api_key: Optional[str] = None,
    api_key_header: str = "X-API-Key",
    use_cache: bool = True,
    cache_service: Optional[str] = None,
    skip_ssl_verify: bool = False,
) -> Union[Dict[str, Any], None]:
    """
    Make an HTTP request to an external API and handle response processing.
    
    Args:
        url: URL to make request to
        method: HTTP method (GET, POST, etc.)
        params: URL parameters for the request (will be copied to avoid modification)
        headers: HTTP headers to include
        data: Data to send in the request body
        timeout: Request timeout in seconds
        retries: Number of retries on failure
        api_key: Optional API key to add to the request
        api_key_header: Header name to use for the API key
        use_cache: Whether to use cache for GET requests
        cache_service: Service name for cache identification (e.g., 'fda', 'rxnav')
        skip_ssl_verify: Whether to skip SSL certificate verification
        
    Returns:
        Parsed JSON response or None if request failed
    """
    # Use a copy of params to avoid modifying the caller's dict
    if params is not None:
        params = params.copy()
    
    if not headers:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "MedicalMCPServer/0.1.0",
        }
    
    # Add API key to headers if provided
    if api_key:
        headers[api_key_header] = api_key
    
    # Try to get from cache for GET requests
    if method.upper() == "GET" and use_cache:
        cache_service = cache_service or extract_service_name(url)
        cache = get_cache(cache_service)
        cached_response = cache.get(url, params or {})
        if cached_response:
            logger.info(f"Using cached response for {url}")
            return cached_response
    
    attempt = 0
    while attempt < retries:
        try:
            # Calculate exponential backoff delay if this is a retry
            if attempt > 0:
                delay = calculate_retry_delay(attempt, base_delay=DEFAULT_RETRY_DELAY)
                logger.info(f"Retrying in {delay:.1f} seconds (attempt {attempt+1}/{retries})...")
                await asyncio.sleep(delay)
            
            async with httpx.AsyncClient(timeout=timeout, verify=not skip_ssl_verify) as client:
                logger.info(f"Making {method} request to {url}")
                
                if method.upper() == "GET":
                    response = await client.get(url, params=params, headers=headers)
                elif method.upper() == "POST":
                    if data:
                        payload = json.dumps(data)
                    else:
                        payload = None
                    response = await client.post(url, params=params, headers=headers, content=payload)
                else:
                    logger.error(f"Unsupported HTTP method: {method}")
                    return None
                
                result = await process_response(response)
                
                # Cache successful GET responses
                if result and method.upper() == "GET" and use_cache:
                    cache_service = cache_service or extract_service_name(url)
                    cache = get_cache(cache_service)
                    cache.set(url, params or {}, result)
                
                return result
        
        except (httpx.RequestError, httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            attempt += 1
            logger.warning(f"Request failed (attempt {attempt}/{retries}): {e}")
            
            if attempt >= retries:
                logger.error(f"Request failed after {retries} attempts: {str(e)}")
                return None
        except Exception as e:
            logger.error(f"Unexpected error during request: {str(e)}")
            return None
    
    return None

async def process_response(response: Response) -> Union[Dict[str, Any], None]:
    """
    Process an HTTP response and handle errors.
    
    Args:
        response: HTTP response object
        
    Returns:
        Parsed JSON response or None if processing failed
    """
    try:
        response.raise_for_status()
        
        # Try to parse response as JSON
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        else:
            # For non-JSON responses, try to parse anyway but log a warning
            logger.warning(f"Response not JSON format. Content-Type: {content_type}")
            try:
                return response.json()
            except json.JSONDecodeError:
                # Special case for XML responses that might be useful
                if "text/xml" in content_type or "application/xml" in content_type:
                    logger.warning("Received XML response, returning text content as data")
                    return {"data": response.text, "format": "xml"}
                
                logger.error(f"Failed to decode response as JSON: {response.text[:200]}...")
                return None
    
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        logger.error(f"HTTP error: {status_code} - {str(e)}")
        
        # Try to extract error information from response
        try:
            error_info = e.response.json()
            logger.error(f"Error response: {error_info}")
        except json.JSONDecodeError:
            logger.error(f"Error response (not JSON): {e.response.text[:200]}...")
            
        # For certain status codes, return a structured error response
        if status_code == 429:
            return {
                "status": "error",
                "error_type": "rate_limit_exceeded",
                "message": "API rate limit exceeded. Try again later or use an API key."
            }
        elif status_code >= 400 and status_code < 500:
            return {
                "status": "error",
                "error_type": "client_error",
                "status_code": status_code,
                "message": f"Client error: {e.response.reason_phrase}"
            }
        elif status_code >= 500:
            return {
                "status": "error",
                "error_type": "server_error",
                "status_code": status_code,
                "message": f"Server error: {e.response.reason_phrase}"
            }
        
        return None
def extract_service_name(url: str) -> str:
    """
    Extract service name from URL for cache identification.
    
    Args:
        url: API endpoint URL
        
    Returns:
        Service name for cache identification
    """
    parsed_url = urlparse(url)
    hostname = parsed_url.netloc.lower()
    
    # Extract the service name from common API hostnames
    if 'api.fda.gov' in hostname:
        return 'fda'
    elif 'rxnav.nlm.nih.gov' in hostname:
        return 'rxnav'
    elif 'eutils.ncbi.nlm.nih.gov' in hostname:
        return 'pubmed'
    elif 'clinicaltrial' in hostname:
        return 'trials'
    
    # Use domain name as fallback
    parts = hostname.split('.')
    if len(parts) > 1:
        return parts[-2]  # e.g., 'example' from 'example.com'
    
    return 'generic'


def calculate_retry_delay(attempt: int, base_delay: float = 1.0, jitter: float = 0.1) -> float:
    """
    Calculate exponential backoff delay with jitter for retries.
    
    Args:
        attempt: Current attempt number (1-based)
        base_delay: Base delay in seconds
        jitter: Random jitter factor (0-1)
        
    Returns:
        Delay in seconds before next retry
    """
    # Exponential backoff: base_delay * 2^(attempt-1)
    delay = base_delay * (2 ** (attempt - 1))
    
    # Add jitter to avoid thundering herd problem
    jitter_amount = delay * jitter
    delay += random.uniform(-jitter_amount, jitter_amount)
    
    return max(0.1, delay)  # Ensure minimum delay


# Function alias to maintain compatibility with existing code
# This ensures the ndc_routes.py file which imports make_api_request still works
make_api_request = make_request
