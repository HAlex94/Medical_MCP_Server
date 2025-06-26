"""
FDA Orange Book Routes

Endpoints for retrieving therapeutic equivalence data from the FDA Orange Book
"""
from fastapi import APIRouter, HTTPException, Query
import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging

from app.utils.api_clients import make_request
from app.utils.api_cache import CACHE_ENABLED

# Emergency override for Render deployment
# Force disable any caching or file system access
RENDER_ENV = os.environ.get("RENDER", "false").lower() == "true"
EMERGENCY_UNCACHED = RENDER_ENV or os.environ.get("EMERGENCY_UNCACHED", "false").lower() == "true"

router = APIRouter()
logger = logging.getLogger(__name__)

class TherapeuticEquivalenceData(BaseModel):
    """Model for a therapeutically equivalent product"""
    appl_no: Optional[str] = None
    product_no: Optional[str] = None
    form: Optional[str] = None
    strength: Optional[str] = None
    reference_drug: Optional[bool] = None
    drug_name: Optional[str] = None
    active_ingredient: Optional[str] = None
    reference_standard: Optional[bool] = None
    te_code: Optional[str] = None  # Therapeutic Equivalence code (e.g., "AB", "AB1")
    applicant: Optional[str] = None
    approval_date: Optional[str] = None
    product_id: Optional[str] = None  # FDA Product ID
    market_status: Optional[str] = None  # e.g., "Prescription"

class OrangeBookResponse(BaseModel):
    """Response model for Orange Book data search"""
    query: str  # What was searched for
    total_results: int
    displayed_results: int
    products: List[TherapeuticEquivalenceData] = []

@router.get("/orange-book/search", response_model=OrangeBookResponse)
async def search_orange_book(
    name: Optional[str] = Query(None, description="Drug name to search for"),
    active_ingredient: Optional[str] = Query(None, description="Active ingredient to search for"),
    appl_no: Optional[str] = Query(None, description="Application number"),
    ndc: Optional[str] = Query(None, description="NDC code"),
    limit: int = Query(10, description="Maximum number of results to return"),
    skip: int = Query(0, description="Number of results to skip for pagination"),
):
    """
    Search the FDA Orange Book for therapeutic equivalence data.
    
    The Orange Book identifies drug products approved by the FDA
    and provides therapeutic equivalence evaluations for approved multi-source
    prescription drug products.
    
    Parameters:
    - name: Drug name (brand or generic)
    - active_ingredient: Active ingredient
    - appl_no: Application number
    - ndc: NDC code
    - limit: Maximum number of results to return
    - skip: Number of results to skip for pagination
    
    Returns:
    - List of products with therapeutic equivalence information
    """
    try:
        # Verify that at least one search parameter is provided
        if not any([name, active_ingredient, appl_no, ndc]):
            raise HTTPException(
                status_code=400, 
                detail="At least one search parameter is required (name, active_ingredient, appl_no, or ndc)"
            )
        
        # Construct the search query based on provided parameters
        search_parts = []
        search_description = ""
        
        if name:
            normalized_name = name.strip().lower()
            # Primary field path that works reliably based on testing
            search_parts.append(f'openfda.brand_name:"{normalized_name}"')
            search_description = f"name: {normalized_name}"
        
        if active_ingredient:
            normalized_ingredient = active_ingredient.strip().lower()
            # Primary field path that works reliably based on testing
            search_parts.append(f'openfda.generic_name:"{normalized_ingredient}"')
            search_description = search_description or f"active ingredient: {normalized_ingredient}"
        
        if appl_no:
            search_parts.append(f'appl_no:"{appl_no}"')
            search_description = search_description or f"application number: {appl_no}"
        
        if ndc:
            # Use openfda.product_ndc path based on testing
            search_parts.append(f'openfda.product_ndc:"{ndc}"')
            search_description = search_description or f"NDC: {ndc}"
        
        # Combine search parts with AND operator
        search_query = "+AND+".join(search_parts)
        
        # FDA API endpoint for Orange Book
        url = f"https://api.fda.gov/drug/drugsfda.json"
        params = {
            "search": search_query,
            "limit": limit,
            "skip": skip
        }
        
        # Try to get the FDA API key if available
        from app.utils.api_clients import get_api_key
        api_key = get_api_key("FDA_API_KEY")
        if api_key:
            params["api_key"] = api_key
            logger.info("Using FDA API key for Orange Book search")
        
        logger.info(f"Searching FDA Orange Book for {search_description}")
        
        # On Render, bypass caching to avoid permission issues
        if EMERGENCY_UNCACHED:
            logger.info("EMERGENCY_UNCACHED mode: Direct API request without caching")
            # Import httpx directly to make the request
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()
        else:
            # Use normal cached request method
            result = await make_request(url, params=params)
        
        if not result or "results" not in result or not result["results"]:
            logger.warning(f"No Orange Book data found for {search_description}")
            return OrangeBookResponse(
                query=search_description,
                total_results=0,
                displayed_results=0,
                products=[]
            )
        
        # Process the response data
        products = []
        for product in result["results"]:
            # Process each product and extract therapeutic equivalence data
            # Handle both old and new FDA API formats
            
            # Get basic product data
            processed_products = []
            
            if "products" in product:
                # Handle the newer API format which includes a products array
                for prod in product.get("products", []):
                    # Extract therapeutic equivalence code if available
                    te_code = None
                    # Check for direct te_code field first (standard format)
                    if prod.get("te_code"):
                        te_code = prod.get("te_code")
                    # Otherwise check for te_ratings array (newer format)
                    elif prod.get("te_ratings"):
                        for rating in prod.get("te_ratings", []):
                            if rating.get("rating_id"):
                                te_code = rating.get("rating_id")
                                break
                    
                    # Create product entry
                    processed_products.append({
                        "appl_no": product.get("application_number"),
                        "product_no": prod.get("product_number"),
                        "form": prod.get("dosage_form", {}).get("form"),
                        "strength": prod.get("active_ingredients", [{}])[0].get("strength") if prod.get("active_ingredients") else None,
                        "reference_drug": prod.get("reference_drug") == "Yes",
                        "drug_name": prod.get("brand_name") or prod.get("proprietary_name"),
                        "active_ingredient": ", ".join([ing.get("name") for ing in prod.get("active_ingredients", [])]) if prod.get("active_ingredients") else None,
                        "reference_standard": prod.get("reference_standard") == "Yes",
                        "te_code": te_code,
                        "applicant": product.get("sponsor_name"),
                        "approval_date": prod.get("approval_date"),
                        "product_id": prod.get("product_id"),  # This is usually related to the NDC
                        "market_status": prod.get("market_status")
                    })
            else:
                # Handle older API format or simple single-product response
                processed_products.append({
                    "appl_no": product.get("application_number"),
                    "product_no": product.get("product_number"),
                    "form": product.get("dosage_form"),
                    "strength": product.get("strength"),
                    "reference_drug": False,  # Default value for older format
                    "drug_name": product.get("trade_name") or product.get("brand_name") or product.get("generic_name"),
                    "active_ingredient": product.get("active_ingredient"),
                    "reference_standard": False,  # Default value for older format
                    "te_code": product.get("te_code"),
                    "applicant": product.get("applicant") or product.get("sponsor_name"),
                    "approval_date": product.get("approval_date"),
                    "product_id": product.get("product_id"),  # This is usually related to the NDC
                    "market_status": product.get("marketing_status")
                })
            
            # Add all processed products to the results
            products.extend(processed_products)
        
        total_results = result.get("meta", {}).get("results", {}).get("total", len(products))
        
        logger.info(f"Found {len(products)} products in the Orange Book for {search_description}")
        
        return OrangeBookResponse(
            query=search_description,
            total_results=total_results,
            displayed_results=len(products),
            products=products
        )
    
    except HTTPException as http_ex:
        # Re-raise HTTP exceptions
        raise http_ex
    
    except Exception as e:
        logger.error(f"Error searching Orange Book: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error searching FDA Orange Book: {str(e)}"
        )


@router.get("/orange-book/equivalent-products", response_model=OrangeBookResponse)
async def find_therapeutic_equivalents(
    ndc: str = Query(..., description="NDC product code to find equivalents for"),
    limit: int = Query(20, description="Maximum number of equivalent products to return"),
    skip: int = Query(0, description="Number of results to skip for pagination"),
):
    """
    Find therapeutically equivalent products for a given NDC product code.
    
    This endpoint:
    1. Looks up the original product by NDC
    2. Finds its active ingredients, dosage form, and strength
    3. Searches for other products with the same parameters
    4. Returns only products with valid therapeutic equivalence codes
    
    Parameters:
    - ndc: NDC product code to find equivalents for
    - limit: Maximum number of equivalent products to return
    - skip: Number of results to skip for pagination
    
    Returns:
    - List of therapeutically equivalent products with their AB ratings
    """
    try:
        # First, get details of the reference product
        original_product = await search_orange_book(ndc=ndc, limit=1, skip=0)
        
        if not original_product.products:
            raise HTTPException(
                status_code=404,
                detail=f"Product with NDC {ndc} not found in FDA Orange Book"
            )
        
        reference = original_product.products[0]
        
        # Now search for therapeutically equivalent products
        # We need to search by active ingredient, dosage form, and strength
        if not reference.active_ingredient:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot find equivalents: active ingredient information is missing for NDC {ndc}"
            )
        
        # Search by active ingredient and form
        search_parts = []
        
        if reference.active_ingredient:
            search_parts.append(f'active_ingredient:"{reference.active_ingredient}"')
        
        if reference.form:
            search_parts.append(f'dosage_form:"{reference.form}"')
        
        # Combine search parts with AND operator
        search_query = "+AND+".join(search_parts)
        
        # FDA API endpoint for Orange Book
        url = f"https://api.fda.gov/drug/drugsfda.json"
        params = {
            "search": search_query,
            "limit": limit + 1,  # +1 to account for the reference product
            "skip": skip
        }
        
        # Try to get the FDA API key if available
        from app.utils.api_clients import get_api_key
        api_key = get_api_key("FDA_API_KEY")
        if api_key:
            params["api_key"] = api_key
        
        logger.info(f"Searching for therapeutic equivalents to {reference.drug_name} (NDC: {ndc})")
        
        # On Render, bypass caching to avoid permission issues
        if EMERGENCY_UNCACHED:
            logger.info("EMERGENCY_UNCACHED mode: Direct API request without caching")
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()
        else:
            # Use normal cached request method
            result = await make_request(url, params=params)
        
        if not result or "results" not in result or not result["results"]:
            logger.warning(f"No equivalent products found for {reference.drug_name}")
            return OrangeBookResponse(
                query=f"Therapeutic equivalents for {reference.drug_name} (NDC: {ndc})",
                total_results=0,
                displayed_results=0,
                products=[]
            )
        
        # Process the response data similar to search_orange_book
        # But only include products with valid therapeutic equivalence codes
        equivalents = []
        
        for product in result["results"]:
            processed_products = []
            
            if "products" in product:
                for prod in product.get("products", []):
                    # Extract therapeutic equivalence code
                    te_code = None
                    # Check for direct te_code field first (standard format)
                    if prod.get("te_code"):
                        te_code = prod.get("te_code")
                    # Otherwise check for te_ratings array (newer format)
                    elif prod.get("te_ratings"):
                        for rating in prod.get("te_ratings", []):
                            if rating.get("rating_id"):
                                te_code = rating.get("rating_id")
                                break
                    
                    # Only include products with therapeutic equivalence codes
                    # and matching strength (if available)
                    if te_code and (not reference.strength or prod.get("active_ingredients", [{}])[0].get("strength") == reference.strength):
                        processed_products.append({
                            "appl_no": product.get("application_number"),
                            "product_no": prod.get("product_number"),
                            "form": prod.get("dosage_form", {}).get("form"),
                            "strength": prod.get("active_ingredients", [{}])[0].get("strength") if prod.get("active_ingredients") else None,
                            "reference_drug": prod.get("reference_drug") == "Yes",
                            "drug_name": prod.get("brand_name") or prod.get("proprietary_name"),
                            "active_ingredient": ", ".join([ing.get("name") for ing in prod.get("active_ingredients", [])]) if prod.get("active_ingredients") else None,
                            "reference_standard": prod.get("reference_standard") == "Yes",
                            "te_code": te_code,
                            "applicant": product.get("sponsor_name"),
                            "approval_date": prod.get("approval_date"),
                            "product_id": prod.get("product_id"),
                            "market_status": prod.get("market_status")
                        })
            else:
                # Handle older API format
                # Check if there's a therapeutic equivalence code
                if product.get("te_code"):
                    # Only include products with therapeutic equivalence codes
                    # and matching strength (if available)
                    if not reference.strength or product.get("strength") == reference.strength:
                        processed_products.append({
                            "appl_no": product.get("application_number"),
                            "product_no": product.get("product_number"),
                            "form": product.get("dosage_form"),
                            "strength": product.get("strength"),
                            "reference_drug": False,
                            "drug_name": product.get("trade_name") or product.get("brand_name") or product.get("generic_name"),
                            "active_ingredient": product.get("active_ingredient"),
                            "reference_standard": False,
                            "te_code": product.get("te_code"),
                            "applicant": product.get("applicant") or product.get("sponsor_name"),
                            "approval_date": product.get("approval_date"),
                            "product_id": product.get("product_id"),
                            "market_status": product.get("marketing_status")
                        })
            
            # Add all processed products to the results
            equivalents.extend(processed_products)
        
        # Filter out the original product from results if it's in the list
        equivalents = [
            prod for prod in equivalents 
            if prod.get("product_id") != ndc
        ]
        
        total_results = len(equivalents)
        
        logger.info(f"Found {total_results} therapeutic equivalents for {reference.drug_name} (NDC: {ndc})")
        
        return OrangeBookResponse(
            query=f"Therapeutic equivalents for {reference.drug_name} (NDC: {ndc})",
            total_results=total_results,
            displayed_results=len(equivalents),
            products=equivalents
        )
    
    except HTTPException as http_ex:
        # Re-raise HTTP exceptions
        raise http_ex
    
    except Exception as e:
        logger.error(f"Error finding therapeutic equivalents: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error finding therapeutic equivalents: {str(e)}"
        )
