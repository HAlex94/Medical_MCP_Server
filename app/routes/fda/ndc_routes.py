from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import asyncio
import logging
import os
from app.utils.api_clients import make_api_request

# Setup logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fda", tags=["FDA"])

class NDCSummaryResponse(BaseModel):
    total_results: int
    displayed_results: int
    products: List[Dict[str, Any]]

@router.get("/ndc/compact_search", response_model=NDCSummaryResponse)
async def search_ndc_compact(
    name: Optional[str] = None,
    manufacturer: Optional[str] = None,
    active_ingredient: Optional[str] = None,
    ndc: Optional[str] = None,
    limit: int = 10,
    skip: int = 0
):
    """
    Search for drug products in the FDA NDC Directory with compact results
    to avoid ResponseTooLargeError issues.
    
    Parameters:
    - name: Brand or generic name of the drug
    - manufacturer: Name of the manufacturer
    - active_ingredient: Active ingredient in the drug
    - ndc: National Drug Code
    - limit: Maximum number of results to return (default: 10)
    - skip: Number of results to skip for pagination (default: 0)
    """
    # Direct FDA API URL with clean, properly formatted search parameters
    # This matches the successful approach from the PillQ application
    
    search_parts = []
    
    if name:
        # This format works reliably with the FDA API - matching PillQ's approach
        search_parts.append(f"(brand_name:{name}+generic_name:{name})")
    if manufacturer:
        search_parts.append(f"openfda.manufacturer_name:{manufacturer}")
    if active_ingredient:
        search_parts.append(f"active_ingredients.name:{active_ingredient}")
    if ndc:
        # Support both product-level NDCs and package-level NDCs
        # For package-level NDCs (e.g., 0088-2219-00), we need to search in packaging.package_ndc
        # For product-level NDCs (e.g., 0088-2219), we search in product_ndc
        
        # Check if this is likely a package-level NDC (contains two hyphens)
        if ndc.count('-') == 2 or len(ndc.split('-')[-1]) == 2:
            # This is likely a package-level NDC, search in packaging.package_ndc
            logger.info(f"Searching for package-level NDC: {ndc}")
            search_parts.append(f"packaging.package_ndc:{ndc}")
        else:
            # This is likely a product-level NDC
            logger.info(f"Searching for product-level NDC: {ndc}")
            search_parts.append(f"product_ndc:{ndc}")
    
    if not search_parts:
        raise HTTPException(status_code=400, detail="At least one search parameter is required")
    
    search_string = "+AND+".join(search_parts)
    
    # FDA API URL with properly formatted search parameters
    url = f"https://api.fda.gov/drug/ndc.json?search={search_string}&limit={limit}&skip={skip}"
    
    logger.info(f"Querying FDA API with URL: {url}")
    
    try:
        logger.info(f"Making FDA API request to: {url}")
        
        # For FDA APIs, we sometimes need to use a direct API key
        # Try first with FDA_API_KEY if available in env
        try:
            import os
            api_key = os.environ.get('FDA_API_KEY')
            if api_key:
                # Add API key to URL if available
                url = f"{url}&api_key={api_key}"
                logger.info("Using FDA API key from environment")
        except Exception as e:
            logger.warning(f"Error getting FDA API key: {str(e)}")
        
        # Special handling for Render deployment - bypass caching
        use_cache = True
        
        # Check if running on Render or emergency uncached mode requested
        if os.environ.get('RENDER') or os.environ.get('EMERGENCY_UNCACHED'):
            logger.warning("Running on Render or emergency mode - bypassing cache to avoid permission issues")
            use_cache = False
        
        response = await make_api_request(url, use_cache=use_cache)
        logger.info(f"Got FDA API response with keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
        
        # Extract only the most important fields for each product
        products = []
        
        if "results" in response:
            total = response.get("meta", {}).get("results", {}).get("total", 0)
            logger.info(f"Found {total} total results, processing {len(response['results'])} products")
            
            for product in response["results"]:
                # Extract packaging information including package_ndc values
                packaging = []
                for package in product.get("packaging", []):
                    packaging.append({
                        "package_ndc": package.get("package_ndc"),
                        "description": package.get("description"),
                        "marketing_start_date": package.get("marketing_start_date"),
                        "sample": package.get("sample", False)
                    })
                
                compact_product = {
                    "product_ndc": product.get("product_ndc"),
                    "brand_name": product.get("brand_name"),
                    "generic_name": product.get("generic_name"),
                    "dosage_form": product.get("dosage_form"),
                    "route": product.get("route"),
                    "marketing_status": product.get("marketing_status"),
                    # Include package-level NDC information
                    "packaging": packaging,
                    "active_ingredients": [
                        {"name": ing.get("name"), "strength": ing.get("strength")}
                        for ing in product.get("active_ingredients", [])
                    ],
                    "manufacturer_name": product.get("openfda", {}).get("manufacturer_name", ["Unknown"])[0] 
                                        if product.get("openfda") else "Unknown"
                }
                products.append(compact_product)
            
            logger.info(f"Successfully processed {len(products)} products")
            return NDCSummaryResponse(
                total_results=total,
                displayed_results=len(products),
                products=products
            )
        else:
            logger.warning(f"No results found in FDA API response. Response keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
            return NDCSummaryResponse(total_results=0, displayed_results=0, products=[])
    
    except Exception as e:
        logger.error(f"Error retrieving NDC data: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving NDC data: {str(e)}"
        )
