#!/usr/bin/env python
"""
Test script for API client with caching implementation
"""
import asyncio
import logging
import sys
from app.utils.api_clients import make_request, get_api_key
from app.utils.api_cache import get_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("test_api_client_caching")

async def test_fda_api_with_caching():
    """Test FDA API with caching"""
    logger.info("Testing FDA API with caching...")
    
    # Get cache instance for FDA API
    cache = get_cache("fda")
    # Clear cache if the method exists
    if hasattr(cache, 'clear'):
        cache.clear()
    
    # FDA NDC Directory API endpoint
    base_url = "https://api.fda.gov/drug/ndc.json"
    
    # Test parameters for a known NDC
    test_ndc = "0002-3232"
    params = {
        "search": f"product_ndc:\"{test_ndc}*\"",
        "limit": 1
    }
    
    # Make first request - should query the API directly
    logger.info("Making first request (uncached)...")
    start_time = asyncio.get_event_loop().time()
    result1 = await make_request(
        url=base_url,
        params=params,
        use_cache=True,
        cache_service="fda",
        api_key=get_api_key("FDA_API_KEY"),
    )
    elapsed1 = asyncio.get_event_loop().time() - start_time
    
    if result1 and "error" not in result1:
        logger.info(f"First request successful in {elapsed1:.2f} seconds")
        if "results" in result1 and len(result1["results"]) > 0:
            product = result1["results"][0]
            logger.info(f"Product found: {product.get('brand_name', 'Unknown')} ({product.get('product_ndc', 'Unknown')})")
    else:
        logger.error(f"First request failed: {result1}")
        return
    
    # Make second request - should use cache
    logger.info("Making second request (should use cache)...")
    start_time = asyncio.get_event_loop().time()
    result2 = await make_request(
        url=base_url,
        params=params,
        use_cache=True,
        cache_service="fda",
        api_key=get_api_key("FDA_API_KEY"),
    )
    elapsed2 = asyncio.get_event_loop().time() - start_time
    
    if result2 and "error" not in result2:
        logger.info(f"Second request successful in {elapsed2:.2f} seconds")
        cache_effectiveness = (elapsed1 / elapsed2) if elapsed2 > 0 else float('inf')
        logger.info(f"Cache effectiveness: {elapsed1:.2f}s vs {elapsed2:.2f}s ({cache_effectiveness:.1f}x faster)")
    else:
        logger.error(f"Second request failed: {result2}")
    
    # Verify both results are identical
    import json
    result1_str = json.dumps(result1, sort_keys=True)
    result2_str = json.dumps(result2, sort_keys=True)
    if result1_str == result2_str:
        logger.info("✅ Results are identical - caching works correctly!")
    else:
        logger.warning("❌ Results differ - potential caching issue")
    
    logger.info("Testing complete!")

async def test_rxnav_api_with_caching():
    """Test RxNav API with caching"""
    logger.info("\nTesting RxNav API with caching...")
    
    # Get cache instance for RxNav API
    cache = get_cache("rxnav")
    # Clear cache if the method exists
    if hasattr(cache, 'clear'):
        cache.clear()
    
    # RxNav API endpoint for getting RxCUI by NDC
    base_url = "https://rxnav.nlm.nih.gov/REST/ndcstatus.json"
    
    # Test parameters for a known NDC
    test_ndc = "00023232"
    params = {
        "ndc": test_ndc
    }
    
    # Make first request - should query the API directly
    logger.info("Making first request (uncached)...")
    start_time = asyncio.get_event_loop().time()
    result1 = await make_request(
        url=base_url,
        params=params,
        use_cache=True,
        cache_service="rxnav"
    )
    elapsed1 = asyncio.get_event_loop().time() - start_time
    
    if result1 and "error" not in result1:
        logger.info(f"First request successful in {elapsed1:.2f} seconds")
        if "ndcStatus" in result1:
            status = result1["ndcStatus"]
            logger.info(f"NDC Status: {status.get('status', 'Unknown')}")
            if "conceptName" in status:
                logger.info(f"Medication: {status.get('conceptName', 'Unknown')}")
            if "rxcui" in status:
                logger.info(f"RxCUI: {status.get('rxcui', 'Unknown')}")
    else:
        logger.error(f"First request failed: {result1}")
        return
    
    # Make second request - should use cache
    logger.info("Making second request (should use cache)...")
    start_time = asyncio.get_event_loop().time()
    result2 = await make_request(
        url=base_url,
        params=params,
        use_cache=True,
        cache_service="rxnav"
    )
    elapsed2 = asyncio.get_event_loop().time() - start_time
    
    if result2 and "error" not in result2:
        logger.info(f"Second request successful in {elapsed2:.2f} seconds")
        cache_effectiveness = (elapsed1 / elapsed2) if elapsed2 > 0 else float('inf')
        logger.info(f"Cache effectiveness: {elapsed1:.2f}s vs {elapsed2:.2f}s ({cache_effectiveness:.1f}x faster)")
    else:
        logger.error(f"Second request failed: {result2}")
    
    # Verify both results are identical
    import json
    result1_str = json.dumps(result1, sort_keys=True)
    result2_str = json.dumps(result2, sort_keys=True)
    if result1_str == result2_str:
        logger.info("✅ Results are identical - caching works correctly!")
    else:
        logger.warning("❌ Results differ - potential caching issue")
    
    logger.info("Testing complete!")

async def main():
    logger.info("Starting API client caching tests...")
    
    await test_fda_api_with_caching()
    await test_rxnav_api_with_caching()
    
    logger.info("All tests completed.")

if __name__ == "__main__":
    asyncio.run(main())
