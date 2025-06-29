"""
DailyMed Session Management

Handles session management, rate limiting, and caching for DailyMed API access.
"""

import logging
import time
import random
from typing import Any, Callable, Dict
from functools import wraps
from datetime import datetime, timedelta
from collections import deque

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Setup logging
logger = logging.getLogger(__name__)

# Constants
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59',
]

# Rate limiting settings
REQUEST_LIMIT = 20
WINDOW_SIZE = 60  # seconds
MIN_INTERVAL = 1  # seconds

# Cache settings
CACHE_EXPIRY = 3600  # 1 hour in seconds

# Request cache for storing previously fetched data
request_cache = {}

def get_random_user_agent() -> str:
    """Return a random user agent from the list."""
    return random.choice(USER_AGENTS)

def create_session() -> requests.Session:
    """Create a requests session with retry capability and random user agent."""
    session = requests.Session()
    
    # Configure retry strategy for transient HTTP errors
    retry_strategy = Retry(
        total=3,  # Maximum number of retries
        backoff_factor=1,  # Exponential backoff factor
        status_forcelist=[429, 500, 502, 503, 504],  # Status codes to retry on
    )
    
    # Apply retry adapter to session
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Set a random user agent
    session.headers.update({
        "User-Agent": get_random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'DNT': '1',  # Do Not Track request header
    })
    
    return session

def rate_limited(func):
    """Decorator to apply rate limiting to API calls."""
    # Use a deque to track request timestamps
    requests_timestamps = deque(maxlen=REQUEST_LIMIT)
    last_request_time = 0
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        nonlocal last_request_time
        
        # Enforce minimum interval between requests
        current_time = time.time()
        time_since_last_request = current_time - last_request_time
        if time_since_last_request < MIN_INTERVAL:
            sleep_time = MIN_INTERVAL - time_since_last_request
            logger.info(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        # Check if we're making too many requests in the time window
        current_time = time.time()
        cutoff_time = current_time - WINDOW_SIZE
        
        # Remove timestamps older than the window
        while requests_timestamps and requests_timestamps[0] < cutoff_time:
            requests_timestamps.popleft()
        
        # If we've reached the limit, sleep until we can make another request
        if len(requests_timestamps) >= REQUEST_LIMIT:
            sleep_time = requests_timestamps[0] - cutoff_time + 0.1  # Add a small buffer
            logger.info(f"Rate limiting: maximum requests reached. Sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
            # After sleeping, recalculate cutoff and remove old timestamps
            current_time = time.time()
            cutoff_time = current_time - WINDOW_SIZE
            while requests_timestamps and requests_timestamps[0] < cutoff_time:
                requests_timestamps.popleft()
        
        # Add current timestamp to the queue and update last request time
        current_time = time.time()
        requests_timestamps.append(current_time)
        last_request_time = current_time
        
        # Execute the wrapped function
        return func(*args, **kwargs)
        
    return wrapper

def get_from_cache_or_fetch(key: str, fetch_func: Callable, *args, **kwargs) -> Any:
    """
    Try to get data from cache or fetch it if not available or expired.
    
    Args:
        key: Cache key
        fetch_func: Function to call to fetch the data if not in cache
        
    Returns:
        Cached or newly fetched data
    """
    now = datetime.now()
    if key in request_cache:
        data, timestamp = request_cache[key]
        if now - timestamp < timedelta(seconds=CACHE_EXPIRY):
            logger.info(f"Using cached data for {key}")
            return data
    
    # Fetch fresh data
    data = fetch_func(*args, **kwargs)
    if data is not None:
        request_cache[key] = (data, now)
    return data
