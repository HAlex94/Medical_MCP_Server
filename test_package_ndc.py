#!/usr/bin/env python3
"""
Test script to verify the package-level NDC search functionality works
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

async def test_package_ndc_search(package_ndc="0088-2219-00"):
    """Test the package-level NDC search functionality"""
    # This mimics our updated search logic in ndc_routes.py
    search_parts = []
    
    # Check if this is likely a package-level NDC (contains two hyphens)
    if package_ndc.count('-') == 2 or len(package_ndc.split('-')[-1]) == 2:
        logger.info(f"Searching for package-level NDC: {package_ndc}")
        search_parts.append(f"packaging.package_ndc:{package_ndc}")
    else:
        logger.info(f"Searching for product-level NDC: {package_ndc}")
        search_parts.append(f"product_ndc:{package_ndc}")
    
    search_string = "+AND+".join(search_parts)
    url = f"https://api.fda.gov/drug/ndc.json?search={search_string}&limit=5"
    
    logger.info(f"Querying FDA API with URL: {url}")
    
    # Use the same cache bypass logic we added to the endpoint
    response = await make_api_request(url, use_cache=False)
    
    if response:
        logger.info(f"Response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
        
        if "results" in response:
            logger.info(f"Found {len(response['results'])} products")
            
            for product in response["results"]:
                product_ndc = product.get("product_ndc")
                brand_name = product.get("brand_name")
                
                logger.info(f"Found product: {brand_name} (Product NDC: {product_ndc})")
                
                # Look at the packaging information
                for package in product.get("packaging", []):
                    package_ndc = package.get("package_ndc")
                    description = package.get("description")
                    logger.info(f"  - Package: {package_ndc} - {description}")
                
                return {
                    "test_result": "SUCCESS",
                    "message": f"Successfully found package-level NDC {package_ndc}",
                    "product": {
                        "product_ndc": product_ndc,
                        "brand_name": brand_name,
                        "packaging": [
                            {
                                "package_ndc": p.get("package_ndc"),
                                "description": p.get("description")
                            } 
                            for p in product.get("packaging", [])
                        ]
                    }
                }
            
            return {
                "test_result": "PARTIAL",
                "message": "API request succeeded but no products found with this package NDC",
                "response": response
            }
        else:
            return {
                "test_result": "FAILED",
                "message": "No results found in FDA API response",
                "response": response
            }
    else:
        return {
            "test_result": "ERROR",
            "message": "No response data received from FDA API"
        }

async def main():
    """Run the test and print results"""
    # Test with a package-level NDC
    result = await test_package_ndc_search("0088-2219-00")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
