"""
FDA Label Information Routes

Specialized routes for retrieving comprehensive drug label information from FDA APIs,
designed for consistent LLM consumption with intelligent fallback mechanisms.
"""
from typing import List, Dict, Any, Optional, Union
from fastapi import APIRouter, HTTPException
import os
import logging
import urllib.parse
from pydantic import BaseModel
from app.utils.api_clients import make_request
from app.utils.api_clients import get_api_key

router = APIRouter()
logger = logging.getLogger(__name__)

# Helper function for safer OpenFDA field extraction
def get_openfda_field(openfda, field, fallback=None):
    """Safely extract a field from OpenFDA data handling both list and string formats"""
    val = openfda.get(field, None)
    if isinstance(val, list):
        return val[0] if val else fallback
    elif isinstance(val, str):
        return val
    return fallback

# Safely get first item from a list or return the value itself
def first_or_value(val, fallback=None):
    """Get first item if list, return value if string, or fallback if neither"""
    if isinstance(val, list) and val:
        return val[0]
    return val if val is not None else fallback

# Ensure a value is always returned as a list for consistent response typing
def to_list(value):
    """Ensure a value is always returned as a list for consistent output typing"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]

# Define important label sections we want to retrieve
IMPORTANT_LABEL_SECTIONS = [
    "indications_and_usage",
    "dosage_and_administration",
    "dosage_forms_and_strengths",
    "contraindications",
    "warnings_and_precautions",
    "adverse_reactions",
    "drug_interactions",
    "use_in_specific_populations",
    "clinical_pharmacology",
    "mechanism_of_action",
    "boxed_warning",
    "warnings",
    "precautions"
]

class LabelSection(BaseModel):
    """Model for a section of a drug label"""
    name: str
    content: str

class DrugLabelResponse(BaseModel):
    """Response model for drug label information"""
    brand_name: Optional[str] = None
    generic_name: Optional[str] = None
    manufacturer: Optional[str] = None
    ndc: Optional[List[str]] = None
    sections: List[LabelSection] = []
    dosage_forms: Optional[List[str]] = None
    route: Optional[List[str]] = None
    application_numbers: Optional[List[str]] = None
    message: Optional[str] = None

async def search_label_info(name=None, active_ingredient=None, ndc=None, limit=25):
    """
    Search FDA label data with a robust fallback strategy to handle FDA's quirky API responses
    
    Returns:
        tuple: (results, successful_strategy) - the FDA API results and which strategy worked
    """
    name_orig = name
    name = name.upper() if name else None
    active_ingredient = active_ingredient.upper() if active_ingredient else None
    
    # Clean NDC format
    ndc_clean = ndc.replace("-", "") if ndc else None
    
    # Ordered list of search strategies to try
    search_orders = []
    
    # 1. Direct NDC lookups (most reliable)
    if ndc_clean:
        search_orders.append((f'openfda.product_ndc:"{ndc_clean}"', "NDC exact match"))
        search_orders.append((f'openfda.product_ndc:{ndc_clean}', "NDC match"))
        search_orders.append((f'openfda.package_ndc:"{ndc_clean}"', "Package NDC exact match"))
    
    # 2. UPPERCASE brand name (preferred form)
    if name:
        search_orders.append((f'openfda.brand_name:"{name}"', "Brand name uppercase"))
        search_orders.append((f'brand_name:"{name}"', "Brand name (non-openfda) uppercase"))
        search_orders.append((f'openfda.generic_name:"{name}"', "Generic name uppercase"))
    
    # 3. UPPERCASE active ingredient (preferred form)
    if active_ingredient:
        search_orders.append((f'openfda.substance_name:"{active_ingredient}"', "Substance name uppercase"))
        search_orders.append((f'openfda.generic_name:"{active_ingredient}"', "Generic name uppercase"))
        
    # 4. Try with non-exact brand name match (catch variants)
    if name:
        search_orders.append((f'openfda.brand_name:{name}', "Brand name partial uppercase"))  # Notice no quotes
        search_orders.append((f'openfda.generic_name:{name}', "Generic name partial uppercase"))

    # 5. Try with non-exact active ingredient match (catch variants)
    if active_ingredient:
        search_orders.append((f'openfda.substance_name:{active_ingredient}', "Substance name partial uppercase"))
        search_orders.append((f'openfda.generic_name:{active_ingredient}', "Generic name partial uppercase"))
        
    # 6. Try original case if all uppercase failed
    if name_orig:
        search_orders.append((f'openfda.brand_name:"{name_orig}"', "Brand name original"))
        search_orders.append((f'openfda.generic_name:"{name_orig}"', "Generic name original"))
        search_orders.append((f'drug_name:"{name_orig}"', "Drug name original"))
    
    # Clean name by removing problematic characters that might interfere with search
    clean_name = name_orig.replace("'", "").replace('"', '').strip()
    if clean_name != name_orig:
        search_orders.append((f'openfda.brand_name:{clean_name}', "Brand name clean"))
    
    # Try each search strategy in order until we get results
    for query, strategy_name in search_orders:
        # URL encode the query to handle special characters
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://api.fda.gov/drug/label.json?search={encoded_query}&limit={limit}"
        
        # Add API key if available (increases rate limits)
        api_key = get_api_key("FDA_API_KEY")
        if api_key:
            url += f"&api_key={api_key}"
            
        logger.info(f"Trying FDA label search with strategy: {strategy_name} - {query}")
        
        try:
            # Make the API request
            result = await make_request(url)
            
            # Check if we got valid results
            if result and "results" in result and result["results"]:
                logger.info(f"Found label data with strategy: {strategy_name}")
                return result["results"], strategy_name
        except Exception as e:
            logger.warning(f"FDA Label search failed for {strategy_name}: {str(e)}")
            continue
    
    # If we've tried all strategies and found nothing
    logger.warning(f"All FDA label search strategies failed, no results found for: name={name}, ingredient={active_ingredient}, ndc={ndc}")
    return [], "No successful strategy"

def extract_label_sections(label_data):
    """Extract important sections from a drug label result"""
    sections = []
    
    # Process all important sections
    for section_name in IMPORTANT_LABEL_SECTIONS:
        if section_name in label_data:
            content = label_data[section_name]
            
            # Handle both string and array formats
            if isinstance(content, list):
                content = " ".join(content)
                
            sections.append(LabelSection(
                name=section_name.replace("_", " ").title(),
                content=content
            ))
    
    return sections

@router.get("/label-info", response_model=DrugLabelResponse)
async def get_label_info(
    name: Optional[str] = Query(None, description="Brand name of the drug"),
    ndc: Optional[str] = Query(None, description="NDC code of the drug"),
    active_ingredient: Optional[str] = Query(None, description="Active ingredient of the drug")
):
    """
    Get comprehensive drug label information including indications, warnings, 
    contraindications, and more. Uses intelligent fallback queries to improve
    reliability compared to direct FDA API access.
    """
    if not name and not ndc and not active_ingredient:
        raise HTTPException(status_code=400, detail="At least one search parameter (name, ndc, or active_ingredient) is required")
        
    try:
        # Search FDA label API with robust fallback logic
        label_results, successful_strategy = await search_label_info(name, active_ingredient, ndc)
        logger.info(f"Successfully found label data using strategy: {successful_strategy}")
        
        if not label_results:
            raise HTTPException(status_code=404, detail="No drug label information found for the provided parameters")
            
        # Get the first label result (most relevant)
        label_data = label_results[0]
        
        # Extract openfda metadata if available
        openfda = label_data.get("openfda", {})
        
        # Extract important sections
        sections = extract_label_sections(label_data)
        
        # Create response using safer field extraction and consistent typing
        # Deduplicate NDCs if they exist
        ndc_list = to_list(openfda.get("product_ndc")) if openfda.get("product_ndc") else ([ndc] if ndc else [])
        if ndc_list:
            ndc_list = list(set(ndc_list))  # Remove duplicates
        
        response = DrugLabelResponse(
            brand_name=get_openfda_field(openfda, "brand_name", name),
            generic_name=get_openfda_field(openfda, "generic_name", active_ingredient),
            manufacturer=get_openfda_field(openfda, "manufacturer_name", "Unknown"),
            ndc=ndc_list,
            sections=sections,
            dosage_forms=to_list(openfda.get("dosage_form")),
            route=to_list(openfda.get("route")),
            application_numbers=to_list(openfda.get("application_number")),
        )
        
        # Add informative messages
        messages = []
        if not sections:
            messages.append("Found drug label but no label sections were available")
            
        # Add a note if multiple results were found but only first is being used
        if len(label_results) > 1:
            messages.append(f"Found {len(label_results)} matching products. Using the first/most relevant result.")
            
        if messages:
            response.message = ". ".join(messages)
            
        return response
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting drug label information: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving drug label information: {str(e)}")
