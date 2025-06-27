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
    source_field: Optional[str] = None  # Which search field/strategy yielded the result
    data_quality: Optional[str] = None  # Indicator if data is missing critical fields

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
        
        # --- Robust FDA Orange Book Fallback Search ---
        # Create search description for logging and response
        search_description = f"name={name} ingredient={active_ingredient} ndc={ndc}"
        
        # Multiple case variants for better search robustness
        name_up = name.upper() if name else None
        name_title = name.title() if name else None
        ingredient_up = active_ingredient.upper() if active_ingredient else None
        ingredient_title = active_ingredient.title() if active_ingredient else None
        ndc_clean = ndc.replace("-", "") if ndc else None

        # Ordered search field strategies with multiple case variants
        search_orders = [
            # NDC searches - most reliable
            (f'openfda.product_ndc:"{ndc_clean}"', "openfda.product_ndc") if ndc_clean else None,
            (f'products.product_ndc:"{ndc_clean}"', "products.product_ndc") if ndc_clean else None,
            
            # UPPERCASE name searches (primary)
            (f'openfda.brand_name:"{name_up}"', "openfda.brand_name.uppercase") if name_up else None,
            (f'openfda.generic_name:"{name_up}"', "openfda.generic_name.uppercase") if name_up else None,
            (f'products.brand_name:"{name_up}"', "products.brand_name.uppercase") if name_up else None,
            
            # UPPERCASE ingredient searches (primary)
            (f'products.active_ingredients.name:"{ingredient_up}"', "products.active_ingredients.name.uppercase") if ingredient_up else None,
            (f'openfda.substance_name:"{ingredient_up}"', "openfda.substance_name.uppercase") if ingredient_up else None,
            (f'openfda.generic_name:"{ingredient_up}"', "openfda.generic_name.uppercase") if ingredient_up else None,
            
            # Title Case name searches (fallback)
            (f'openfda.brand_name:"{name_title}"', "openfda.brand_name.titlecase") if name_title else None,
            (f'openfda.generic_name:"{name_title}"', "openfda.generic_name.titlecase") if name_title else None,
            (f'products.brand_name:"{name_title}"', "products.brand_name.titlecase") if name_title else None,
            
            # Title Case ingredient searches (fallback)
            (f'products.active_ingredients.name:"{ingredient_title}"', "products.active_ingredients.name.titlecase") if ingredient_title else None,
            (f'openfda.substance_name:"{ingredient_title}"', "openfda.substance_name.titlecase") if ingredient_title else None,
            (f'openfda.generic_name:"{ingredient_title}"', "openfda.generic_name.titlecase") if ingredient_title else None,
            
            # First word only fallbacks (even more robust)
            (f'openfda.brand_name:"{name_up.split()[0]}"', "openfda.brand_name.firstword") if name_up and ' ' in name_up else None,
            (f'openfda.generic_name:"{ingredient_up.split()[0]}"', "openfda.generic_name.firstword") if ingredient_up and ' ' in ingredient_up else None,
        ]
        search_orders = [x for x in search_orders if x]

        result = None
        used_query = None
        used_field = None
        for query, field in search_orders:
            url = "https://api.fda.gov/drug/drugsfda.json"
            params = {
                "search": query,
                "limit": limit,
                "skip": skip
            }
            from app.utils.api_clients import get_api_key
            api_key = get_api_key("FDA_API_KEY")
            if api_key:
                params["api_key"] = api_key
            logger.info(f"Trying Orange Book search with {field}: {query}")
            try:
                if EMERGENCY_UNCACHED:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        response = await client.get(url, params=params)
                        response.raise_for_status()
                        result = response.json()
                else:
                    result = await make_request(url, params=params)
                if result and "results" in result and result["results"]:
                    used_query = query
                    used_field = field
                    logger.info(f"Found Orange Book results with {field}")
                    break
                else:
                    logger.debug(f"No results for {field} strategy")
                    continue
            except Exception as e:
                logger.warning(f"FDA Orange Book search failed for {field}: {e}")
                continue

        if not result or "results" not in result or not result["results"]:
            logger.warning(f"No Orange Book data found for any search strategy")
            return OrangeBookResponse(
                query=f"No results for {name or ''} {active_ingredient or ''} {ndc or ''}",
                total_results=0,
                displayed_results=0,
                products=[]
            )
        
        # Process the response data
        products = []
        for product in result["results"]:
            # Process each product and extract therapeutic equivalence data
            # Handle both old and new FDA API formats
            
            # Process each product - handles different FDA API formats
            processed_products = []
            if "products" in product:  # New FDA API format with nested products
                for item in product["products"]:
                    # Get therapeutic equivalence code
                    te_code = None
                    if "te_code" in item:
                        te_code = item["te_code"]
                    elif "te_ratings" in item and item["te_ratings"]:
                        # Extract from te_ratings if available
                        if isinstance(item["te_ratings"], list) and len(item["te_ratings"]) > 0:
                            te_code = item["te_ratings"][0].get("te_code")
                    
                    # Skip items without therapeutic equivalence data
                    if not te_code:
                        continue
                    
                    # Check data quality - whether critical fields are present
                    missing_fields = []
                    if not item.get("brand_name") and not item.get("proprietary_name"):
                        missing_fields.append("name")
                    if not item.get("active_ingredient"):
                        missing_fields.append("ingredient")
                    if not item.get("dosage_form") and not (isinstance(item.get("dosage_form"), dict) and item["dosage_form"].get("form")):
                        missing_fields.append("form")
                    
                    data_quality = None
                    if missing_fields:
                        data_quality = f"Missing: {', '.join(missing_fields)}"
                    
                    processed_products.append(TherapeuticEquivalenceData(
                        appl_no=product.get("application_number"),
                        product_no=item.get("product_number"),
                        form=item.get("dosage_form", {}).get("form") if isinstance(item.get("dosage_form"), dict) else item.get("dosage_form"),
                        strength=item.get("strength"),
                        reference_drug=item.get("reference_drug") == "Yes",
                        drug_name=item.get("brand_name", item.get("proprietary_name")),
                        active_ingredient=item.get("active_ingredient"),
                        reference_standard=item.get("reference_standard") == "Yes",
                        te_code=te_code,
                        applicant=product.get("sponsor_name"),
                        approval_date=item.get("approval_date"),
                        product_id=item.get("product_id"),  # This is usually related to the NDC
                        market_status=item.get("marketing_status"),
                        source_field=used_field,  # Store which search strategy yielded the result
                        data_quality=data_quality  # Store information about missing critical fields
                    ))
            else:
                # Handle older API format or simple single-product response
                processed_products.append(TherapeuticEquivalenceData(
                    appl_no=product.get("application_number"),
                    product_no=product.get("product_number"),
                    form=product.get("dosage_form"),
                    strength=product.get("strength"),
                    reference_drug=False,
                    drug_name=product.get("trade_name") or product.get("brand_name") or product.get("generic_name"),
                    active_ingredient=product.get("active_ingredient"),
                    reference_standard=False,
                    te_code=product.get("te_code"),
                    applicant=product.get("applicant") or product.get("sponsor_name"),
                    approval_date=product.get("approval_date"),
                    product_id=product.get("product_id"),  # This is usually related to the NDC
                    market_status=product.get("marketing_status"),
                    source_field=used_field,  # Store which search strategy yielded the result
                    data_quality=None  # No data quality check for older format
                ))
            
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
