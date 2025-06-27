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

class AutoDiscoverLabelResponse(BaseModel):
    """Response model for auto-discovered label data"""
    success: bool = True
    drug_name: str
    ndc: Optional[str] = None
    found_field: str
    section_content: str
    all_sections: List[LabelSection] = []
    route: Optional[List[str]] = None
    application_numbers: Optional[List[str]] = None
    search_strategy: str
    ndcs_tried: List[str] = []
    message: Optional[str] = None

async def lookup_ndcs_for_name(name: str, limit: int = 10) -> List[str]:
    """
    Look up all NDCs for a drug name using FDA NDC Directory.
    This helps bridge drug names to specific NDCs for more reliable label lookups.
    """
    if not name:
        return []
        
    # Try multiple case variants
    name_up = name.upper()
    name_title = name.title()
    
    # Search strategies in order of reliability
    search_queries = [
        (f'brand_name:"{name_up}"', "Brand name uppercase"),
        (f'generic_name:"{name_up}"', "Generic name uppercase"),
        (f'brand_name:"{name_title}"', "Brand name titlecase"),
        (f'generic_name:"{name_title}"', "Generic name titlecase")
    ]
    
    # Try first word only if it's a multi-word name
    first_word = name.split()[0] if len(name.split()) > 1 else None
    if first_word:
        search_queries.append((f'brand_name:"{first_word.upper()}"', "Brand name first word"))
        search_queries.append((f'generic_name:"{first_word.upper()}"', "Generic name first word"))
    
    # URL for FDA NDC API
    base_url = "https://api.fda.gov/drug/ndc.json"
    ndcs = []
    
    for query, strategy in search_queries:
        if len(ndcs) >= limit:
            break
            
        try:
            # URL encode the query
            encoded_query = urllib.parse.quote_plus(query)
            url = f"{base_url}?search={encoded_query}&limit={limit}"
            
            # Add API key if available
            api_key = get_api_key("FDA_API_KEY")
            if api_key:
                url += f"&api_key={api_key}"
            
            logger.info(f"Looking up NDCs with {strategy}: {query}")
            result = await make_request(url)
            
            if result and "results" in result and result["results"]:
                for product in result["results"]:
                    if "product_ndc" in product:
                        ndc = product["product_ndc"]
                        if ndc not in ndcs:
                            ndcs.append(ndc)
                            
                # If we found NDCs with this strategy, log success
                if ndcs:
                    logger.info(f"Found {len(ndcs)} NDCs using {strategy}")
        except Exception as e:
            logger.warning(f"NDC lookup failed with {strategy}: {str(e)}")
            continue
    
    # Return unique NDCs up to the limit
    return ndcs[:limit]

async def try_label_for_field(ndc: str, field: str) -> Optional[Dict]:
    """
    Try to retrieve label data for an NDC and check if the specified field exists.
    Returns the label data if the field is present, otherwise None.
    """
    if not ndc:
        return None
        
    # Clean NDC format
    ndc_clean = ndc.replace("-", "") if ndc else None
    
    try:
        # URL encode the query
        query = f'openfda.product_ndc:"{ndc_clean}"'
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://api.fda.gov/drug/label.json?search={encoded_query}&limit=1"
        
        # Add API key if available
        api_key = get_api_key("FDA_API_KEY")
        if api_key:
            url += f"&api_key={api_key}"
            
        logger.info(f"Checking if field '{field}' exists in label for NDC {ndc_clean}")
        result = await make_request(url)
        
        if result and "results" in result and result["results"]:
            label = result["results"][0]
            
            # Check if the desired field exists and has content
            if field in label and label[field]:
                content = label[field]
                if isinstance(content, list):
                    content = " ".join(content)
                
                logger.info(f"Found field '{field}' in label for NDC {ndc_clean}")
                return {
                    "label": label,
                    "field": field,
                    "content": content
                }
            else:
                logger.info(f"Field '{field}' not found in label for NDC {ndc_clean}")
    except Exception as e:
        logger.warning(f"Label lookup failed for NDC {ndc_clean}: {str(e)}")
    
    return None

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

# Important label sections frequently accessed by medical applications
IMPORTANT_LABEL_SECTIONS = [
    "indications_and_usage", "dosage_and_administration", "dosage_forms_and_strengths",
    "contraindications", "warnings_and_precautions", "adverse_reactions", "drug_interactions",
    "use_in_specific_populations", "clinical_pharmacology", "mechanism_of_action",
    "boxed_warning", "warnings", "precautions", "pregnancy", "nursing_mothers",
    "pediatric_use", "geriatric_use", "overdosage", "how_supplied", "storage_and_handling"
]

def extract_all_sections(label: Dict) -> List[LabelSection]:
    """
    Extract all important label sections present in the label data.
    This provides a consistent and comprehensive view of all available sections.
    """
    sections = []
    
    # Process all important sections that exist in the label
    for section_name in IMPORTANT_LABEL_SECTIONS:
        if section_name in label and label[section_name]:
            content = label[section_name]
            if isinstance(content, list):
                content = " ".join(content)
            
            # Convert snake_case to Title Case for display
            display_name = section_name.replace("_", " ").title()
            
            sections.append(LabelSection(name=display_name, content=content))
            
    return sections

@router.get("/label/auto-discover", response_model=AutoDiscoverLabelResponse)
async def auto_discover_label(
    name: str = None, 
    field: str = None,
    ndc_limit: int = 10,
    last_ditch: bool = True
):
    """
    Auto-discover a drug label section by trying all NDCs for a drug name.
    
    This endpoint uses a multi-stage search strategy:
    1. Find all NDCs for the drug name
    2. Try each NDC to find a label with the requested field
    3. If none found, try fallback search strategies
    
    Parameters:
    - name: Drug name (brand or generic)
    - field: FDA label field to find (e.g., indications_and_usage, boxed_warning)
    - ndc_limit: Maximum number of NDCs to try
    - last_ditch: Whether to try last-ditch _exists_ search if all else fails
    
    Returns a label with the requested field, including all other available sections.
    """
    if not name:
        raise HTTPException(status_code=400, detail="Drug name is required")
        
    if not field:
        raise HTTPException(status_code=400, detail="Label field is required")
    
    # Normalize the field name to match FDA API format
    field = field.lower().replace(" ", "_")
    
    logger.info(f"Auto-discovering label field '{field}' for drug '{name}'")
    
    # Track NDCs tried
    ndcs_tried = []
    search_strategy = ""
    
    try:
        # STEP 1: Find all NDCs for the name
        ndcs = await lookup_ndcs_for_name(name, limit=ndc_limit)
        if not ndcs:
            logger.warning(f"No NDCs found for drug '{name}'")
            
        # STEP 2: Try each NDC to find a label with the requested field
        for ndc in ndcs:
            ndcs_tried.append(ndc)
            result = await try_label_for_field(ndc, field)
            
            if result:
                # Found the field in this NDC's label!
                label = result["label"]
                search_strategy = f"NDC lookup: {ndc}"
                
                # Extract OpenFDA details if available
                drug_name = name
                active_ingredient = None
                if "openfda" in label:
                    openfda = label["openfda"]
                    if "brand_name" in openfda and openfda["brand_name"]:
                        drug_name = openfda["brand_name"][0]
                    if "substance_name" in openfda and openfda["substance_name"]:
                        active_ingredient = ", ".join(openfda["substance_name"])
                
                # Extract route and application numbers if available
                route = None
                application_numbers = None
                if "openfda" in label:
                    openfda = label["openfda"]
                    if "route" in openfda and openfda["route"]:
                        route = openfda["route"]
                    if "application_number" in openfda and openfda["application_number"]:
                        application_numbers = openfda["application_number"]
                
                # Extract all available sections
                all_sections = extract_all_sections(label)
                
                # Format the response
                return AutoDiscoverLabelResponse(
                    success=True,
                    drug_name=drug_name,
                    ndc=ndc,
                    found_field=field,
                    section_content=result["content"],
                    all_sections=all_sections,
                    route=route,
                    application_numbers=application_numbers,
                    search_strategy=search_strategy,
                    ndcs_tried=ndcs_tried,
                    message=f"Found {field} for {name} using NDC {ndc}"
                )
        
        # STEP 3: If no NDCs had the field, try a last-ditch search using _exists_
        if last_ditch and not search_strategy:
            logger.info(f"Trying last-ditch _exists_ search for field '{field}'")
            
            # URL encode the query for the specific field using _exists_
            query = f'_exists_:{field} AND openfda.brand_name:"{name.upper()}"'
            encoded_query = urllib.parse.quote_plus(query)
            url = f"https://api.fda.gov/drug/label.json?search={encoded_query}&limit=1"
            
            # Add API key if available
            api_key = get_api_key("FDA_API_KEY")
            if api_key:
                url += f"&api_key={api_key}"
                
            result = await make_request(url)
            
            if result and "results" in result and result["results"]:
                label = result["results"][0]
                
                # If the field exists
                if field in label and label[field]:
                    search_strategy = f"_exists_ search: {field}"
                    
                    # Extract content
                    content = label[field]
                    if isinstance(content, list):
                        content = " ".join(content)
                    
                    # Extract NDC if available
                    ndc = None
                    drug_name = name
                    active_ingredient = None
                    route = None
                    application_numbers = None
                    
                    if "openfda" in label:
                        openfda = label["openfda"]
                        if "product_ndc" in openfda and openfda["product_ndc"]:
                            ndc = openfda["product_ndc"][0]
                            ndcs_tried.append(ndc)
                        if "brand_name" in openfda and openfda["brand_name"]:
                            drug_name = openfda["brand_name"][0]
                        if "substance_name" in openfda and openfda["substance_name"]:
                            active_ingredient = ", ".join(openfda["substance_name"])
                        if "route" in openfda and openfda["route"]:
                            route = openfda["route"]
                        if "application_number" in openfda and openfda["application_number"]:
                            application_numbers = openfda["application_number"]
                    
                    # Extract all available sections
                    all_sections = extract_all_sections(label)
                    
                    # Format the response
                    return AutoDiscoverLabelResponse(
                        success=True,
                        drug_name=drug_name,
                        ndc=ndc,
                        found_field=field,
                        section_content=content,
                        all_sections=all_sections,
                        route=route,
                        application_numbers=application_numbers,
                        search_strategy=search_strategy,
                        ndcs_tried=ndcs_tried,
                        message=f"Found {field} for {name} using last-ditch _exists_ search"
                    )
        
        # If we got here, no data found with the field
        raise HTTPException(
            status_code=404, 
            detail=f"No label with field '{field}' found for drug '{name}' after trying {len(ndcs_tried)} NDCs"
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error in auto-discover label: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving label field: {str(e)}")

