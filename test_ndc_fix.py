#!/usr/bin/env python3
"""
Test script to verify the NDC endpoint changes work properly with caching disabled
This simulates what would happen in the Render environment
"""

import os
import asyncio
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set EMERGENCY_UNCACHED to test our fix
os.environ["EMERGENCY_UNCACHED"] = "1"

# Import the make_api_request function that our endpoint would use
from app.utils.api_clients import make_api_request

async def test_ndc_search():
    """Test the NDC search functionality directly with caching disabled"""
    # This mimics the search logic in the ndc_routes.py file
    name = "atorvastatin"
    search_parts = []
    
    if name:
        search_parts.append(f"(brand_name:{name}+generic_name:{name})")
    
    search_string = "+AND+".join(search_parts)
    url = f"https://api.fda.gov/drug/ndc.json?search={search_string}&limit=5"
    
    logger.info(f"Querying FDA API with URL: {url}")
    
    # Use the same cache bypass logic we added to the endpoint
    use_cache = True
    if os.environ.get('RENDER') or os.environ.get('EMERGENCY_UNCACHED'):
        logger.warning("Running on Render or emergency mode - bypassing cache to avoid permission issues")
        use_cache = False
    
    try:
        # This is what would happen in the actual endpoint
        response = await make_api_request(url, use_cache=use_cache)
        if response:
            # Check if we got expected NDC data
            logger.info(f"Response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
            
            # Extract the same fields our endpoint would extract
            if "results" in response:
                first_result = response["results"][0] if response["results"] else None
                if first_result:
                    product_ndc = first_result.get("product_ndc")
                    brand_name = first_result.get("brand_name")
                    generic_name = first_result.get("generic_name")
                    
                    logger.info(f"Product NDC: {product_ndc}")
                    logger.info(f"Brand name: {brand_name}")
                    logger.info(f"Generic name: {generic_name}")
                    
                    # This would confirm our endpoint works properly
                    return {
                        "test_result": "SUCCESS",
                        "message": "NDC endpoint successfully retrieved product_ndc data",
                        "data": {
                            "product_ndc": product_ndc,
                            "brand_name": brand_name,
                            "generic_name": generic_name
                        }
                    }
            
            return {
                "test_result": "PARTIAL",
                "message": "API request succeeded but response format unexpected",
                "response": response
            }
        else:
            return {
                "test_result": "FAILED",
                "message": "No response data received from FDA API"
            }
    
    except Exception as e:
        logger.error(f"Error testing NDC search: {str(e)}")
        return {
            "test_result": "ERROR",
            "message": f"Exception occurred: {str(e)}"
        }

async def main():
    """Run the test and print results"""
    result = await test_ndc_search()
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
