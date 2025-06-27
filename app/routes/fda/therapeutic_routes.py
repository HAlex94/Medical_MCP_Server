"""
Therapeutic Equivalence Routes

Specialized routes for retrieving therapeutic equivalence data from FDA APIs,
designed for consistent LLM consumption.
"""
from typing import List, Optional, Dict, Any, Tuple
from fastapi import APIRouter, Query, HTTPException
import httpx
import os
import logging
import re
from pydantic import BaseModel
from app.utils.api_clients import make_request
from app.utils.api_clients import get_api_key

router = APIRouter()
logger = logging.getLogger("app.routes.fda")

def normalize_ndc(ndc: str) -> str:
    """Normalize NDC by removing dashes and spaces for consistent lookup
    
    Args:
        ndc: NDC code that may contain dashes or other formatting
        
    Returns:
        Cleaned NDC suitable for FDA API queries
    """
    if not ndc:
        return ""
    # Remove dashes, spaces, and any other non-alphanumeric characters
    return re.sub(r'[^a-zA-Z0-9]', '', ndc)


async def get_ndc_from_name(name: str) -> Optional[str]:
    """
    Get a product NDC for a given drug name using multiple search strategies
    This helps bridge the gap between drug names and the more reliable NDC-based searches
    
    Args:
        name: Drug name to search for
        
    Returns:
        First matching product_ndc or None if not found
    """
    if not name:
        return None
    
    # Try multiple case variants
    name_up = name.upper()
    name_title = name.title()
    
    # Ordered search strategies
    search_queries = [
        (f'brand_name:"{name_up}"', "Brand name uppercase"),
        (f'generic_name:"{name_up}"', "Generic name uppercase"),
        (f'brand_name:"{name_title}"', "Brand name titlecase"),
        (f'generic_name:"{name_title}"', "Generic name titlecase"),
        (f'brand_name:"{name}"', "Brand name original"),
    ]
    
    # Try first word only if it's a multi-word name
    first_word = name.split()[0] if len(name.split()) > 1 else None
    if first_word:
        search_queries.append((f'brand_name:"{first_word.upper()}"', "Brand name first word"))
        search_queries.append((f'generic_name:"{first_word.upper()}"', "Generic name first word"))
    
    # Build FDA NDC API endpoint
    base_url = "https://api.fda.gov/drug/ndc.json"
    
    for query, strategy in search_queries:
        try:
            # Build query with API key if available
            url = f"{base_url}?search={query}&limit=1"
            api_key = get_api_key("FDA_API_KEY")
            if api_key:
                url += f"&api_key={api_key}"
                
            logger.info(f"Searching NDC directory with strategy: {strategy} - {query}")
            result = await make_request(url)
            
            if result and "results" in result and result["results"]:
                # Extract the product_ndc from the first result
                ndc = result["results"][0].get("product_ndc")
                if ndc:
                    logger.info(f"Found NDC {ndc} using strategy: {strategy}")
                    return ndc
        except Exception as e:
            logger.warning(f"NDC lookup failed for {strategy}: {str(e)}")
            continue
    
    logger.warning(f"No NDC found for drug name: {name}")
    return None

# Models for the response
class EquivalentProduct(BaseModel):
    """Model for a therapeutically equivalent product"""
    brand_name: str
    manufacturer: Optional[str] = None
    ndc: Optional[str] = None
    application_number: Optional[str] = None
    te_code: Optional[str] = None
    dosage_form: Optional[str] = None
    strength: Optional[str] = None
    reference_drug: Optional[bool] = False

class TherapeuticEquivalenceResponse(BaseModel):
    """Response model for therapeutic equivalence data with enhanced LLM-friendly fields"""
    success: bool = True
    brand_name: Optional[str] = None
    active_ingredient: Optional[str] = None
    ndc: Optional[str] = None
    te_codes: List[str] = []
    reference_drug: bool = False
    reference_product: Optional[EquivalentProduct] = None
    equivalent_products: List[EquivalentProduct] = []
    # TE code grouping for easier LLM consumption
    grouped_by_te_code: Optional[Dict[str, List[EquivalentProduct]]] = None
    # Reference drug detection metadata
    reference_drug_warning: Optional[str] = None
    # Standard diagnostics
    message: Optional[str] = None
    search_method: Optional[str] = None
    search_attempts: Optional[List[str]] = []
    available_fields: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

async def find_reference_product(name=None, active_ingredient=None, ndc=None):
    """Find a reference product using different search strategies with enhanced fallback logic"""
    # Build a comprehensive set of search strategies
    search_strategies = []
    
    # Strategy 1: If we have an NDC, that's the most specific identifier
    if ndc:
        # Clean up NDC format - ensure consistent normalization across all NDC lookups
        clean_ndc = normalize_ndc(ndc)
        search_strategies.append((f"openfda.product_ndc:\"{clean_ndc}\"", "NDC product"))
        search_strategies.append((f"products.product_ndc:\"{clean_ndc}\"", "NDC products"))
        search_strategies.append((f"openfda.package_ndc:\"{clean_ndc}\"", "NDC package"))
        search_strategies.append((f"_exists_:openfda.product_ndc AND {clean_ndc}", "NDC anywhere"))
    
    # Strategy 2: If we have a name, try with multiple case variants (FDA can be case-sensitive)
    if name:
        # Prepare name variants (FDA API can be case-sensitive)
        name_up = name.upper()  # FDA often indexes in UPPERCASE
        name_title = name.title()  # Sometimes title case works better
        name_orig = name  # Original case as provided
        
        # Clean up common formatting issues
        # Remove common suffixes like tabs, capsules, etc.
        suffixes = [" tablets", " tabs", " tab", " capsules", " capsule", " injection", " oral", 
                   " cream", " ointment", " solution", " powder", " tablet"]
        
        # Also clean up trailing numbers and dosages
        clean_name_up = re.sub(r'\s+\d+\s*(?:mg|mcg|ml|g|%)?$', '', name_up)
        clean_name_title = re.sub(r'\s+\d+\s*(?:mg|mcg|ml|g|%)?$', '', name_title)
        clean_name_orig = re.sub(r'\s+\d+\s*(?:mg|mcg|ml|g|%)?$', '', name_orig)
        
        # Apply suffix removal if needed
        for suffix in suffixes:
            suffix_up = suffix.upper()
            if clean_name_up.endswith(suffix_up):
                clean_name_up = clean_name_up[:-len(suffix_up)].strip()
            
            suffix_title = suffix.title()
            if clean_name_title.endswith(suffix_title):
                clean_name_title = clean_name_title[:-len(suffix_title)].strip()
                
            if clean_name_orig.lower().endswith(suffix.lower()):
                clean_name_orig = clean_name_orig[:-(len(suffix))].strip()
        
        # Try quotes removed (helps with names that have apostrophes)
        quote_free_name = name.replace("'", "").replace("\"", "").strip()
        
        # Try UPPERCASE first (most FDA data is indexed as uppercase)
        search_strategies.append((f"openfda.brand_name:\"{name_up}\"", "Brand UP"))
        search_strategies.append((f"brand_name:\"{name_up}\"", "Direct brand UP"))
        if clean_name_up != name_up:
            search_strategies.append((f"openfda.brand_name:\"{clean_name_up}\"", "Brand clean UP"))
        
        # Try Title Case second
        search_strategies.append((f"openfda.brand_name:\"{name_title}\"", "Brand Title"))
        search_strategies.append((f"brand_name:\"{name_title}\"", "Direct brand Title"))
        if clean_name_title != name_title:
            search_strategies.append((f"openfda.brand_name:\"{clean_name_title}\"", "Brand clean Title"))
        
        # Try original case (lowest priority)
        search_strategies.append((f"openfda.brand_name:\"{name_orig}\"", "Brand original"))
        search_strategies.append((f"brand_name:\"{name_orig}\"", "Direct brand original"))
        if clean_name_orig != name_orig:
            search_strategies.append((f"openfda.brand_name:\"{clean_name_orig}\"", "Brand clean original"))
            
        # Try with quotes removed (helps with names that have apostrophes)
        if quote_free_name != name:
            search_strategies.append((f"openfda.brand_name:\"{quote_free_name}\"", "Brand quotes removed"))
        
        # Sometimes brand names are in the application data
        search_strategies.append((f"application_docs.application_docs_list.submission_property_type:Established Name AND \"{name_up}\"", "App docs"))
    
    # Strategy 3: If we have active ingredient, try with multiple case variants
    if active_ingredient:
        # Prepare variants
        ingredient_up = active_ingredient.upper()
        ingredient_title = active_ingredient.title()
        ingredient_orig = active_ingredient
        
        # Try UPPERCASE first
        search_strategies.append((f"openfda.generic_name:\"{ingredient_up}\"", "Generic UP"))
        search_strategies.append((f"openfda.substance_name:\"{ingredient_up}\"", "Substance UP"))
        search_strategies.append((f"products.active_ingredients.name:\"{ingredient_up}\"", "Active ingredients UP"))
        
        # Try Title Case
        search_strategies.append((f"openfda.generic_name:\"{ingredient_title}\"", "Generic Title"))
        search_strategies.append((f"openfda.substance_name:\"{ingredient_title}\"", "Substance Title"))
        
        # Try original case
        search_strategies.append((f"openfda.generic_name:\"{ingredient_orig}\"", "Generic original"))
        search_strategies.append((f"openfda.substance_name:\"{ingredient_orig}\"", "Substance original"))
        search_strategies.append((f"_exists_:active_ingredients AND \"{ingredient_orig}\"", "Active ingredients"))
    
    # Strategy 4: If name but no active ingredient, try name as active ingredient
    # (sometimes brand names and active ingredients overlap)
    if name and not active_ingredient:
        search_strategies.append((f"openfda.generic_name:\"{name_up}\"", "Name as generic UP"))
        search_strategies.append((f"openfda.substance_name:\"{name_up}\"", "Name as substance UP"))
    
    # Try each strategy until we find something
    reference_product = None
    results_found = False
    
    for search_query, strategy_name in search_strategies:
        try:
            logger.info(f"Trying {strategy_name} strategy with query: {search_query}")
            url = f"https://api.fda.gov/drug/drugsfda.json?search={search_query}&limit=25"
            api_key = get_api_key("FDA_API_KEY")
            if api_key:
                url += f"&api_key={api_key}"
            
            response = await make_request(url)
            
            if response and "results" in response and response["results"]:
                results_found = True
                logger.info(f"Found {len(response['results'])} results using {strategy_name} strategy")
                
                # First pass: Look specifically for reference drugs
                for product_data in response["results"]:
                    if "products" in product_data:
                        for product in product_data["products"]:
                            # Check all possible reference drug indicators
                            is_reference = False
                            reference_indicators = [
                                product.get("reference_drug") == "Yes",
                                product.get("reference_standard") == "Yes",
                                product.get("reference_listed_drug") == "Yes",
                                product.get("reference") == "Yes"
                            ]
                            
                            if any(reference_indicators):
                                is_reference = True
                            
                            # For brand name drugs with no reference indication but matching the search name,
                            # also consider them reference products if they have a brand name
                            if name and product.get("brand_name") and not is_reference:
                                brand = product.get("brand_name", "")
                                if brand and (name.upper() in brand.upper() or brand.upper() in name.upper()):
                                    # Brand name match without explicit reference flag is still likely reference
                                    is_reference = True
                                    logger.info(f"Inferring reference status for brand match: {brand}")
                            
                            if is_reference:
                                brand = product.get("brand_name", name)
                                sponsor_name = product_data.get("sponsor_name", "Unknown")
                                
                                # Extract NDC from all possible locations
                                ndc_value = None
                                if "openfda" in product_data:
                                    if "product_ndc" in product_data["openfda"]:
                                        if isinstance(product_data["openfda"]["product_ndc"], list):
                                            ndc_value = product_data["openfda"]["product_ndc"][0]
                                        else:
                                            ndc_value = product_data["openfda"]["product_ndc"]
                                
                                if not ndc_value and "product_ndc" in product:
                                    ndc_value = product.get("product_ndc")
                                    
                                reference_product = {
                                    "brand_name": brand,
                                    "manufacturer": sponsor_name,
                                    "application_number": product_data.get("application_number"),
                                    "te_code": product.get("te_code"),
                                    "ndc": ndc_value, 
                                    "reference_drug": True
                                }
                                
                                # If this is an exact brand match, return immediately
                                if name and (name.lower() == brand.lower()):
                                    logger.info(f"Found exact reference match for {name}")
                                    return reference_product
                
                # If we found any reference product, return it even if not exact match
                if reference_product:
                    logger.info(f"Found reference product (not exact): {reference_product['brand_name']}")
                    return reference_product
                
                # Second pass: No explicit reference drug, assume the brand name product is reference
                # when name is provided
                if name:
                    for product_data in response["results"]:
                        if "products" in product_data:
                            for product in product_data["products"]:
                                brand = product.get("brand_name", "")
                                if brand and name.lower() in brand.lower() or brand.lower() in name.lower():
                                    sponsor_name = product_data.get("sponsor_name", "Unknown")
                                    logger.info(f"Using brand name match as reference: {brand}")
                                    return {
                                        "brand_name": brand,
                                        "manufacturer": sponsor_name,
                                        "application_number": product_data.get("application_number"),
                                        "te_code": product.get("te_code"),
                                        "reference_drug": product.get("reference_drug") == "Yes"
                                    }
                
                # Last resort: just use the first product found
                if response["results"] and "products" in response["results"][0]:
                    product = response["results"][0]["products"][0]
                    sponsor_name = response["results"][0].get("sponsor_name", "Unknown")
                    logger.info(f"Using first product as reference: {product.get('brand_name', 'Unknown')}")
                    return {
                        "brand_name": product.get("brand_name", name or "Unknown"),
                        "manufacturer": sponsor_name,
                        "application_number": response["results"][0].get("application_number"),
                        "te_code": product.get("te_code"),
                        "reference_drug": product.get("reference_drug") == "Yes"
                    }
        
        except Exception as e:
            logger.error(f"Error with {strategy_name} strategy: {str(e)}")
            continue
    
    if not results_found:
        logger.warning(f"No results found for drug: name={name}, ingredient={active_ingredient}, ndc={ndc}")
    
    return None

async def find_equivalent_products(reference_product, active_ingredient=None):
    """Find therapeutically equivalent products for a reference product"""
    if not reference_product:
        return []
        
    equivalent_products = []
    search_queries = []
    
    # Try multiple search strategies with different case variants
    if active_ingredient:
        # Prepare case variants for active ingredient
        ingredients = [
            active_ingredient.upper(),  # FDA often indexes in UPPERCASE
            active_ingredient.title(),  # Sometimes title case works better
            active_ingredient  # Original case as provided
        ]
        
        for ingredient in ingredients:
            search_queries.append((f"openfda.generic_name:\"{ingredient}\"", f"Generic {ingredient}"))
            search_queries.append((f"openfda.substance_name:\"{ingredient}\"", f"Substance {ingredient}"))
    
    # Also try finding by brand name with different case variants
    if reference_product and 'brand_name' in reference_product and reference_product['brand_name']:
        brand_variants = [
            reference_product['brand_name'].upper(),
            reference_product['brand_name'].title(),
            reference_product['brand_name']
        ]
        
        for brand in brand_variants:
            search_queries.append((f"openfda.brand_name:\"{brand}\"", f"Brand {brand}"))
    
    # Try all search queries until we find results
    results_found = False
    
    for search_query, strategy_name in search_queries:
        if results_found:
            break
            
        try:
            logger.info(f"Finding equivalents with {strategy_name}: {search_query}")
            url = f"https://api.fda.gov/drug/drugsfda.json?search={search_query}&limit=100"
            api_key = get_api_key("FDA_API_KEY")
            if api_key:
                url += f"&api_key={api_key}"
                
            response = await make_request(url)
            
            if response and "results" in response and len(response["results"]) > 0:
                results_found = True
                logger.info(f"Found {len(response['results'])} results using {strategy_name}")
                
                for product_data in response["results"]:
                    if "products" in product_data:
                        sponsor_name = product_data.get("sponsor_name", "Unknown")
                        for product in product_data["products"]:
                            # Skip if it's the reference product
                            if (product.get("brand_name") == reference_product.get("brand_name") and
                                product_data.get("application_number") == reference_product.get("application_number")):
                                continue
                                
                            # Only include products with therapeutic equivalence codes
                            if product.get("te_code"):
                                # Extract strength and dosage form
                                strength = None
                                if "active_ingredients" in product and product["active_ingredients"]:
                                    if isinstance(product["active_ingredients"], list):
                                        strength = product["active_ingredients"][0].get("strength")
                                    else:
                                        strength = product["active_ingredients"].get("strength")
                                        
                                if not strength:
                                    strength = product.get("strength")
                                    
                                # Get dosage form
                                dosage_form = None
                                if isinstance(product.get("dosage_form"), dict):
                                    dosage_form = product["dosage_form"].get("form")
                                else:
                                    dosage_form = product.get("dosage_form")
                                    
                                # Enhanced NDC extraction from all possible locations
                                ndc = None
                                # Check in product's openfda section
                                if "openfda" in product_data:
                                    if "product_ndc" in product_data["openfda"]:
                                        if isinstance(product_data["openfda"]["product_ndc"], list) and product_data["openfda"]["product_ndc"]:
                                            ndc = product_data["openfda"]["product_ndc"][0]
                                        elif isinstance(product_data["openfda"]["product_ndc"], str):
                                            ndc = product_data["openfda"]["product_ndc"]
                                            
                                    # Try package_ndc if product_ndc not available
                                    if not ndc and "package_ndc" in product_data["openfda"]:
                                        if isinstance(product_data["openfda"]["package_ndc"], list) and product_data["openfda"]["package_ndc"]:
                                            ndc = product_data["openfda"]["package_ndc"][0]
                                        elif isinstance(product_data["openfda"]["package_ndc"], str):
                                            ndc = product_data["openfda"]["package_ndc"]
                                
                                # Check in product itself if not found in openfda
                                if not ndc and "product_ndc" in product:
                                    ndc = product.get("product_ndc")
                                
                                # Add to equivalent products
                                equivalent_products.append(EquivalentProduct(
                                    brand_name=product.get("brand_name", "Generic"),
                                    manufacturer=sponsor_name,
                                    ndc=ndc,
                                    application_number=product_data.get("application_number"),
                                    te_code=product.get("te_code"),
                                    dosage_form=dosage_form,
                                    strength=strength,
                                    reference_drug=(product.get("reference_drug") == "Yes" or 
                                                  product.get("reference_standard") == "Yes" or
                                                  product.get("reference_listed_drug") == "Yes")
                                ))
        except Exception as e:
            logger.error(f"Error with {strategy_name} search: {str(e)}")
            continue
    
    return equivalent_products

@router.get("/therapeutic-equivalence", response_model=TherapeuticEquivalenceResponse)
async def get_therapeutic_equivalence(
    name: Optional[str] = Query(None, description="Drug brand name to search for"),
    ndc: Optional[str] = Query(None, description="NDC code to search for"),
    active_ingredient: Optional[str] = Query(None, description="Active ingredient to search for"),
    te_code: Optional[str] = Query(None, description="Filter by specific therapeutic equivalence code (e.g., 'AB', 'AB1')"),
    group_by_te_code: bool = Query(False, description="Group equivalent products by their TE code for easier analysis"),
    fields: Optional[str] = Query(None, description="Comma-separated fields to include in response")
):
    """Get therapeutic equivalence information for a drug
    
    At least one of name, ndc, or active_ingredient must be provided.
    """
    if not any([name, ndc, active_ingredient]):
        raise HTTPException(status_code=400, detail="At least one of name, ndc, or active_ingredient must be provided")
    
    try:
        logger.info(f"Therapeutic equivalence request - name: '{name}', ndc: '{ndc}', active_ingredient: '{active_ingredient}'")
        
        # Track which search strategy ultimately succeeded
        successful_strategy = ""
        search_trail = []
        
        # STEP 1: Try with NDC first if provided (most reliable lookup)
        reference_product = None
        if ndc:
            search_trail.append(f"Direct NDC search: {ndc}")
            reference_product = await find_reference_product(None, None, ndc)
            if reference_product:
                successful_strategy = "Direct NDC search"
        
        # STEP 2: If no direct NDC match but name provided, try to get NDC from name
        if not reference_product and name:
            search_trail.append(f"Chained NDC lookup from name: {name}")
            derived_ndc = await get_ndc_from_name(name)
            
            if derived_ndc:
                logger.info(f"Found NDC {derived_ndc} via name lookup for {name}")
                search_trail.append(f"Using derived NDC: {derived_ndc}")
                
                # Try looking up products using the derived NDC
                reference_product = await find_reference_product(None, None, derived_ndc)
                if reference_product:
                    successful_strategy = "Derived NDC from name"
        
        # STEP 3: If still no match, try with the original name search
        if not reference_product and name:
            search_trail.append(f"Name-based search: {name}")
            reference_product = await find_reference_product(name, active_ingredient, None)
            if reference_product:
                successful_strategy = "Name search"
        
        # STEP 4: If still no match but have active ingredient, try that
        if not reference_product and active_ingredient:
            search_trail.append(f"Active ingredient search: {active_ingredient}")
            reference_product = await find_reference_product(None, active_ingredient, None)
            if reference_product:
                successful_strategy = "Active ingredient search"
            
        # STEP 5: Try name normalization for common drug form suffixes 
        if not reference_product and name:
            # Remove common suffixes like tabs, capsules, etc.
            suffixes = [" tabs", " tab", " capsules", " capsule", " injection", " oral", 
                       " cream", " ointment", " solution", " powder", " tablet"]
            cleaned_name = name.lower()
            for suffix in suffixes:
                if cleaned_name.endswith(suffix):
                    cleaned_name = cleaned_name[:-len(suffix)].strip()
                    break
            
            if cleaned_name != name.lower():
                search_trail.append(f"Normalized name search: {cleaned_name}")
                logger.info(f"Trying with normalized name: {cleaned_name}")
                reference_product = await find_reference_product(cleaned_name, active_ingredient, None)
                if reference_product:
                    successful_strategy = "Normalized name search"
        
        # If we couldn't find a reference product after all attempts
        if not reference_product:
            search_attempts = ", ".join(search_trail)
            logger.warning(f"Could not find reference product after all attempts: {search_attempts}")
            # Ensure error response has similar structure to success for LLM consistency
            return TherapeuticEquivalenceResponse(
                success=False,
                message=f"Could not find reference product for {name or active_ingredient or ndc} after trying: {search_attempts}",
                reference_product=None,
                equivalent_products=[],
                search_method="none",
                search_attempts=search_trail,
                available_fields=[],
                metadata={
                    "query_parameters": {
                        "ndc": ndc,
                        "name": name,
                        "active_ingredient": active_ingredient,
                        "te_code": te_code
                    },
                    "error": "Reference product not found after multiple search strategies"
                }
            )
        
        # If we found a reference product, extract its active ingredient if we don't already have one
        if reference_product and not active_ingredient and "active_ingredients" in reference_product:
            active_ingredient = reference_product["active_ingredients"]
            logger.info(f"Using active ingredient from reference product: {active_ingredient}")
            
        # Then find therapeutically equivalent products
        equivalent_products = await find_equivalent_products(reference_product, active_ingredient)
        
        # TE code filtering if specified
        filtered_products = equivalent_products
        if te_code and equivalent_products:
            te_code = te_code.upper()  # Normalize for case-insensitive comparison
            filtered_products = [
                product for product in equivalent_products
                if product.te_code and product.te_code.startswith(te_code)
            ]
            search_trail.append(f"TE code filtering: {te_code}")
            logger.info(f"Filtered to {len(filtered_products)} products with TE code {te_code}")
        
        # Field selection logic
        selected_fields = None
        if fields:
            selected_fields = [f.strip().lower() for f in fields.split(",") if f.strip()]
            search_trail.append(f"Field selection: {fields}")
            logger.info(f"Selected fields: {selected_fields}")
        
        # Get available fields from the products for response metadata
        available_fields = []
        if filtered_products:
            # Extract field names from the first product
            sample_product = filtered_products[0]
            # Get fields from the model - compatible with different Pydantic versions
            available_fields = sorted([
                field_name for field_name in dir(sample_product) 
                if not field_name.startswith('_') and not callable(getattr(sample_product, field_name))
            ])
        
        # Check for multiple reference drugs (potential FDA data inconsistency)
        reference_drug_warning = None
        reference_drug_count = sum(1 for p in filtered_products if getattr(p, 'reference_drug', False))
        if reference_drug_count > 1:
            reference_drug_warning = f"Found {reference_drug_count} products marked as reference drugs. This may indicate FDA data inconsistency."
            logger.warning(reference_drug_warning)
        
        # Group products by TE code if requested
        grouped_products = None
        if group_by_te_code and filtered_products:
            grouped_products = {}
            for product in filtered_products:
                te_code_key = product.te_code if product.te_code else "Unknown"
                if te_code_key not in grouped_products:
                    grouped_products[te_code_key] = []
                grouped_products[te_code_key].append(product)
            
            # Sort groups by code for consistent ordering
            grouped_products = {k: grouped_products[k] for k in sorted(grouped_products.keys())}
        
        # Create response with consistent model fields and enhanced metadata
        response = TherapeuticEquivalenceResponse(
            success=True,
            brand_name=reference_product.get('brand_name'),
            active_ingredient=active_ingredient,
            ndc=reference_product.get('ndc'),
            te_codes=[reference_product.get('te_code')] if reference_product.get('te_code') else [],
            reference_drug=reference_product.get('reference_drug', False),
            reference_product=EquivalentProduct(**reference_product) if isinstance(reference_product, dict) else reference_product,
            equivalent_products=filtered_products,
            grouped_by_te_code=grouped_products,
            reference_drug_warning=reference_drug_warning,
            search_method=successful_strategy,
            search_attempts=search_trail,
            available_fields=available_fields,
            metadata={
                "reference_product": {
                    "ndc": reference_product.get('ndc'),
                    "name": reference_product.get('brand_name'),
                    "active_ingredient": active_ingredient
                },
                "te_code_filter": te_code,
                "selected_fields": selected_fields,
                "total_equivalents": len(equivalent_products),
                "filtered_equivalents": len(filtered_products)
            }
        )
        
        # Add appropriate message based on filtering results
        if not equivalent_products:
            response.message = "Found reference drug but no therapeutically equivalent products"
        elif not filtered_products and equivalent_products:
            response.message = f"Found {len(equivalent_products)} equivalent products, but none match the TE code filter '{te_code}'"
        else:
            filtered_message = ""
            if te_code and len(filtered_products) != len(equivalent_products):
                filtered_message = f" ({len(filtered_products)} after filtering for TE code '{te_code}')"
                
            response.message = f"Found {len(equivalent_products)} therapeutically equivalent products{filtered_message}"
            
            # Add grouping information if applicable
            if grouped_products:
                te_code_summary = ", ".join([f"{code}: {len(prods)}" for code, prods in grouped_products.items()])
                response.message += f". Grouped by TE code: {te_code_summary}"
        
        logger.info(f"Found reference product: {reference_product['brand_name']} with {len(filtered_products)} equivalent products after filtering")
        return response
    except Exception as e:
        logger.error(f"Error getting therapeutic equivalence: {str(e)}", exc_info=True)
        
        # Provide a consistent error response with metadata
        return TherapeuticEquivalenceResponse(
            success=False,
            message=f"Error getting therapeutic equivalence: {str(e)}",
            search_method="error",
            search_attempts=search_trail if 'search_trail' in locals() else [],
            metadata={
                "query_parameters": {
                    "ndc": ndc,
                    "name": name,
                    "active_ingredient": active_ingredient,
                    "te_code": te_code
                },
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
