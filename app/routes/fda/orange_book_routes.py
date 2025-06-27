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
    search_strategy: Optional[str] = None  # Which strategy found the results
    strategies_attempted: List[str] = []   # All strategies that were attempted
    available_fields: List[str] = []       # Available fields in the products
    metadata: Dict[str, Any] = {}          # Additional metadata about the search

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
        strategies_attempted = []
        
        # Track search rate limiting and errors
        rate_limited = False
        search_errors = []
        
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
            
            # Track strategy attempts for transparency
            strategies_attempted.append(field)
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
                error_msg = str(e)
                search_errors.append(f"{field}: {error_msg}")
                if "429" in error_msg or "rate limit" in error_msg.lower():
                    rate_limited = True
                logger.warning(f"FDA Orange Book search failed for {field}: {e}")
                continue

        if not result or "results" not in result or not result["results"]:
            logger.warning(f"No Orange Book data found for any search strategy")
            
            # Create a descriptive message with helpful information
            message = f"No results for {name or ''} {active_ingredient or ''} {ndc or ''}"
            if rate_limited:
                message += ". API rate limits may have been reached. Consider adding an FDA_API_KEY for higher limits."
                
            # Detect if we tried all strategies without success
            if len(strategies_attempted) > 0:
                message += f" ({len(strategies_attempted)} search strategies attempted)"
                
            # Return structured response even when no results found
            return OrangeBookResponse(
                query=message,
                total_results=0,
                displayed_results=0,
                products=[],
                search_strategy="none",
                strategies_attempted=strategies_attempted,
                available_fields=["ndc", "name", "active_ingredient", "appl_no", "te_code"],
                metadata={
                    "errors": search_errors,
                    "rate_limited": rate_limited,
                    "search_parameters": {
                        "name": name,
                        "active_ingredient": active_ingredient,
                        "ndc": ndc,
                        "appl_no": appl_no
                    }
                }
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
        
        # Determine available fields from the products
        available_fields = set()
        if products:
            # Extract field names from the first product
            sample_product = products[0].dict()
            available_fields = set([k for k, v in sample_product.items() if v is not None])
            available_fields = sorted(list(available_fields))
        
        # Return the enhanced results with metadata
        return OrangeBookResponse(
            query=search_description,
            total_results=len(products),
            displayed_results=len(products),
            products=products,
            search_strategy=used_field,
            strategies_attempted=strategies_attempted,
            available_fields=available_fields,
            metadata={
                "successful_query": used_query,
                "errors": search_errors,
                "rate_limited": rate_limited,
                "search_parameters": {
                    "name": name,
                    "active_ingredient": active_ingredient,
                    "ndc": ndc,
                    "appl_no": appl_no
                }
            }
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
    te_code: Optional[str] = Query(None, description="Filter by specific TE code (e.g., 'AB', 'AB1')"),
    fields: Optional[str] = Query(None, description="Comma-separated fields to include in response"),
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
            strategies_attempted = ["reference_product_search"]
            
            if te_code:
                strategies_attempted.append(f"te_code_filter:{te_code}")
            
            return OrangeBookResponse(
                query=f"Therapeutic equivalents for {reference.drug_name} (NDC: {ndc})",
                total_results=0,
                displayed_results=0,
                products=[],
                search_strategy="active_ingredient_and_form_search",
                strategies_attempted=strategies_attempted,
                available_fields=["ndc", "name", "active_ingredient", "form", "strength", "te_code"],
                metadata={
                    "reference_product": {
                        "ndc": ndc,
                        "name": reference.drug_name,
                        "active_ingredient": reference.active_ingredient,
                        "form": reference.form,
                        "strength": reference.strength
                    },
                    "te_code_filter": te_code,
                    "message": "No equivalent products found that match the criteria"
                }
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
        
        # Apply TE code filtering if specified
        strategies_attempted = ["reference_product_search"]
        filtered_equivalents = equivalents
        if te_code:
            te_code = te_code.upper()  # Normalize for case-insensitive comparison
            filtered_equivalents = [
                product for product in equivalents
                if product.get("te_code") and product.get("te_code").startswith(te_code)
            ]
            strategies_attempted.append(f"te_code_filter:{te_code}")
            logger.info(f"Filtered to {len(filtered_equivalents)} products with TE code {te_code}")
        
        # Field selection logic
        selected_fields = None
        if fields:
            selected_fields = [f.strip().lower() for f in fields.split(",") if f.strip()]
            strategies_attempted.append(f"field_selection:{','.join(selected_fields)}")
            logger.info(f"Selected fields: {selected_fields}")
        
        # Get available fields from the products for response metadata
        available_fields = []
        if filtered_equivalents:
            # Extract field names from the first product
            sample_product = filtered_equivalents[0]
            available_fields = sorted([k for k, v in sample_product.items() if v is not None])
        
        total_results = len(filtered_equivalents)
        
        logger.info(f"Found {total_results} therapeutic equivalents for {reference.drug_name} (NDC: {ndc})")
        
        # Enhanced response with metadata
        return OrangeBookResponse(
            query=f"Therapeutic equivalents for {reference.drug_name} (NDC: {ndc})",
            total_results=total_results,
            displayed_results=len(filtered_equivalents),
            products=filtered_equivalents,
            search_strategy="active_ingredient_and_form_search",
            strategies_attempted=strategies_attempted,
            available_fields=available_fields,
            metadata={
                "reference_product": {
                    "ndc": ndc,
                    "name": reference.drug_name,
                    "active_ingredient": reference.active_ingredient,
                    "form": reference.form,
                    "strength": reference.strength
                },
                "te_code_filter": te_code,
                "selected_fields": selected_fields
            }
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
