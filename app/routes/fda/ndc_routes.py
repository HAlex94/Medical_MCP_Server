from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx
import asyncio
from app.utils.api_clients import make_api_request

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
    # Build search query
    search_terms = []
    if name:
        search_terms.append(f'generic_name:"{name}" brand_name:"{name}"~')
    if manufacturer:
        search_terms.append(f'manufacturername:"{manufacturer}"~')
    if active_ingredient:
        search_terms.append(f'active_ingredients.name:"{active_ingredient}"~')
    if ndc:
        search_terms.append(f'product_ndc:"{ndc}"~')
    
    if not search_terms:
        raise HTTPException(status_code=400, detail="At least one search parameter is required")
    
    search_query = " AND ".join(search_terms)
    
    # FDA API URL with search parameters
    url = f"https://api.fda.gov/drug/ndc.json?search=({search_query})&limit={limit}&skip={skip}"
    
    try:
        response = await make_api_request(url)
        
        # Extract only the most important fields for each product
        products = []
        
        if "results" in response:
            total = response.get("meta", {}).get("results", {}).get("total", 0)
            for product in response["results"]:
                compact_product = {
                    "product_ndc": product.get("product_ndc"),
                    "brand_name": product.get("brand_name"),
                    "generic_name": product.get("generic_name"),
                    "dosage_form": product.get("dosage_form"),
                    "route": product.get("route"),
                    "marketing_status": product.get("marketing_status"),
                    "active_ingredients": [
                        {"name": ing.get("name"), "strength": ing.get("strength")}
                        for ing in product.get("active_ingredients", [])
                    ],
                    "manufacturer_name": product.get("openfda", {}).get("manufacturer_name", ["Unknown"])[0] 
                                        if product.get("openfda") else "Unknown"
                }
                products.append(compact_product)
            
            return NDCSummaryResponse(
                total_results=total,
                displayed_results=len(products),
                products=products
            )
        else:
            return NDCSummaryResponse(total_results=0, displayed_results=0, products=[])
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving NDC data: {str(e)}"
        )
