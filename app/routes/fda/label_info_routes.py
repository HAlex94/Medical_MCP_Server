"""
FDA Label Information Routes

Specialized routes for retrieving comprehensive drug label information from FDA APIs,
designed for consistent LLM consumption with intelligent fallback mechanisms.
"""
from typing import List, Dict, Any, Optional, Union, Set
from fastapi import APIRouter, HTTPException, Query
import os
import logging
import urllib.parse
from pydantic import BaseModel, Field
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
    metadata: Optional[Dict[str, Any]] = None

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
    ndc_clean = ndc.replace("-", "") if ndc else ""
    
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
    ndc_clean = ndc.replace("-", "") if ndc else ""
    
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

# Field aliases to handle common variations in field names
FIELD_ALIASES = {
    # Boxed warning variations
    "black_box_warning": "boxed_warning",
    "black_box": "boxed_warning",
    "warnings_boxed": "boxed_warning",
    "boxed_warnings": "boxed_warning",
    "black_box_warnings": "boxed_warning",
    
    # Indications variations
    "indications": "indications_and_usage",
    "usage": "indications_and_usage",
    
    # Warnings variations
    "warning": "warnings",
    "warning_and_precautions": "warnings_and_precautions",
    "precautions_and_warnings": "warnings_and_precautions",
    
    # Dosage variations
    "dosage": "dosage_and_administration",
    "dose": "dosage_and_administration",
    "administration": "dosage_and_administration",
    
    # Adverse reactions variations
    "side_effects": "adverse_reactions", 
    "adverse_effects": "adverse_reactions",
    
    # Drug interactions variations
    "interactions": "drug_interactions",
    
    # Special populations variations
    "special_populations": "use_in_specific_populations",
    "specific_populations": "use_in_specific_populations",
    
    # Clinical pharmacology variations
    "pharmacology": "clinical_pharmacology",
    
    # Pregnancy variations
    "pregnancy_category": "pregnancy",
    
    # How supplied variations
    "supplied": "how_supplied",
    "supply": "how_supplied"
}

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


# --- Unified LLM-optimized Label Discovery Endpoint ---

class FieldResult(BaseModel):
    """Results for a specific label field"""
    field: str
    found: bool
    content: Optional[str] = None
    ndc: Optional[str] = None
    ndcs_tried: List[str] = []
    search_strategy: Optional[str] = None
    all_sections: List[LabelSection] = []
    message: Optional[str] = None
    truncated: bool = False
    original_length: Optional[int] = None

class SizeOptimizationMetadata(BaseModel):
    """Metadata about size optimization"""
    applied: bool = False
    max_content_length: Optional[int] = None
    truncated_fields: List[str] = []
    total_characters_saved: int = 0

class LLMLabelDiscoverResponse(BaseModel):
    """Response model for the LLM-optimized label discovery endpoint"""
    success: bool = True
    drug_name: str
    fields: List[FieldResult] = []
    message: Optional[str] = None
    all_ndcs_tried: List[str] = []
    available_fields: List[str] = []
    search_strategies_used: List[str] = []
    metadata: Dict[str, Any] = Field(default_factory=dict)

@router.get("/label/llm-discover", response_model=LLMLabelDiscoverResponse)
async def llm_label_discover(
    name: Optional[str] = Query(None, description="Brand or generic name of the drug"),
    ndc: Optional[str] = Query(None, description="NDC code of the drug (optional, increases accuracy)"),
    fields: Optional[str] = Query(None, description="Comma-separated list of label fields to retrieve (e.g., 'boxed_warning,indications_and_usage'). If not provided, returns all available."),
    ndc_limit: int = Query(10, description="Max number of NDCs to try if name given"),
    last_ditch: bool = Query(True, description="If True, will try a last-ditch _exists_: search for each field if all else fails"),
    max_content_length: Optional[int] = Query(10000, description="Maximum character length for each field content before truncation"),
    max_size: bool = Query(True, description="Apply size optimization to prevent LLM context overflows"),
    include_metadata: bool = Query(False, description="Include full OpenFDA metadata in response (increases size)"),
):
    """
    Unified, robust endpoint to discover FDA drug label data for one or more fields, with multi-strategy fallback.
    
    This endpoint combines the best features of label/search and label/auto-discover in a single LLM-optimized interface.
    It automatically tries multiple search strategies to maximize the chance of finding each requested field.
    
    Parameters:
    - name: Drug name (brand or generic, required if NDC not provided)
    - ndc: NDC code (optional, used first if present)
    - fields: Comma-separated label fields to retrieve (or leave blank for all important sections)
    - ndc_limit: Number of NDCs to try per name if needed
    - last_ditch: Try a final _exists_ search if all else fails
    
    Returns:
    - For each field: content, which NDC found it, all NDCs tried, search strategy, and all available sections from that label.
    """
    if not name and not ndc:
        raise HTTPException(status_code=400, detail="Either 'name' or 'ndc' must be provided")
    
    # Parse requested fields or use all important ones if none specified
    requested_fields = []
    available_fields = []
    
    if fields:
        # Check for special 'ALL' request
        if fields.upper() == 'ALL':
            requested_fields = IMPORTANT_LABEL_SECTIONS
        else:
            # Process each field and apply aliases
            raw_fields = [f.strip().lower().replace(" ", "_") for f in fields.split(",") if f.strip()]
            
            for field in raw_fields:
                # Check if it's an alias and normalize
                if field in FIELD_ALIASES:
                    requested_fields.append(FIELD_ALIASES[field])
                else:
                    requested_fields.append(field)
    
    if not requested_fields:
        requested_fields = IMPORTANT_LABEL_SECTIONS
        
    # List of all available FDA label fields for reference
    available_fields = list(set(IMPORTANT_LABEL_SECTIONS + list(FIELD_ALIASES.values())))
    available_fields.sort()
    
    # Track global information about the search
    all_ndcs_tried = set()
    field_results = []
    drug_name = name or "Unknown"
    
    logger.info(f"LLM label discover request - name: '{name}', ndc: '{ndc}', fields: {requested_fields}")
    
    try:
        # STEP 1: Build list of NDCs to try
        candidate_ndcs = []
        
        # If specific NDC provided, use it first
        if ndc:
            # Clean NDC format - safely handle potential None values
            ndc_clean = ndc.replace("-", "") if ndc else ""
            candidate_ndcs.append(ndc_clean)
            all_ndcs_tried.add(ndc_clean)
        
        # Then try NDCs looked up by name
        if name:
            name_ndcs = await lookup_ndcs_for_name(name, limit=ndc_limit)
            for name_ndc in name_ndcs:
                if name_ndc not in candidate_ndcs:
                    candidate_ndcs.append(name_ndc)
                    all_ndcs_tried.add(name_ndc)
        
        # If we have no NDCs at all, fail early
        if not candidate_ndcs:
            if name:
                raise HTTPException(status_code=404, detail=f"No NDCs found for drug '{name}'")
            else:
                raise HTTPException(status_code=404, detail=f"Invalid NDC: {ndc}")
        
        # STEP 2: Process each requested field
        for field in requested_fields:
            field_result = FieldResult(
                field=field,
                found=False,
                ndcs_tried=[]  
            )
            
            # Try each NDC for this field
            for candidate_ndc in candidate_ndcs:
                field_result.ndcs_tried.append(candidate_ndc)
                
                try:
                    result = await try_label_for_field(candidate_ndc, field)
                    
                    if result:
                        # We found the field in this NDC's label!
                        label = result["label"]
                        field_result.found = True
                        field_result.content = result["content"]
                        field_result.ndc = candidate_ndc
                        field_result.search_strategy = f"NDC lookup: {candidate_ndc}"
                        
                        # Extract drug name if better than what we have
                        if "openfda" in label and "brand_name" in label["openfda"] and label["openfda"]["brand_name"]:
                            drug_name = label["openfda"]["brand_name"][0]
                        
                        # Get all sections from this label
                        field_result.all_sections = extract_all_sections(label)
                        field_result.message = f"Found {field} using NDC {candidate_ndc}"
                        break
                except Exception as e:
                    logger.warning(f"Error checking field {field} for NDC {candidate_ndc}: {str(e)}")
            
            # If field not found in any NDC, try substance name fallback
            if not field_result.found and name:
                try:
                    logger.info(f"Trying substance/generic name fallback search for field '{field}'")
                    
                    # Try by active ingredient/substance name
                    query = f'_exists_:{field} AND openfda.substance_name:"{name.upper()}"'
                    encoded_query = urllib.parse.quote_plus(query)
                    url = f"https://api.fda.gov/drug/label.json?search={encoded_query}&limit=1"
                    
                    # Add API key if available
                    api_key = get_api_key("FDA_API_KEY")
                    if api_key:
                        url += f"&api_key={api_key}"
                    
                    result = await make_request(url)
                    
                    if result and "results" in result and result["results"]:
                        label = result["results"][0]
                        if field in label and label[field]:
                            field_result.found = True
                            content = label[field]
                            if isinstance(content, list):
                                content = " ".join(content)
                                
                            # Apply content length restriction if max_size is enabled
                            if max_size and max_content_length > 0 and len(content) > max_content_length:
                                original_length = len(content)
                                content = content[:max_content_length] + f"... [truncated, {original_length-max_content_length} more characters]"
                                field_result.truncated = True
                                field_result.original_length = original_length
                            
                            field_result.content = content
                            field_result.search_strategy = f"Substance name search: {name}"
                            
                            # Extract NDC if available
                            if "openfda" in label and "product_ndc" in label["openfda"] and label["openfda"]["product_ndc"]:
                                field_result.ndc = label["openfda"]["product_ndc"][0]
                                all_ndcs_tried.add(field_result.ndc)
                                field_result.ndcs_tried.append(field_result.ndc)
                            
                            # Get all sections from this label
                            field_result.all_sections = extract_all_sections(label)
                            field_result.message = f"Found {field} using substance name search"
                            break
                except Exception as e:
                    logger.warning(f"Substance name search failed for field {field}: {str(e)}")
            
            # If field still not found, try last-ditch _exists_ search
            if not field_result.found and last_ditch:
                try:
                    logger.info(f"Trying last-ditch _exists_ search for field '{field}'")
                    
                    # URL encode the query for the specific field using _exists_
                    query = f'_exists_:{field}'
                    
                    # Add name filter if available
                    if name:
                        query += f' AND openfda.brand_name:"{name.upper()}"'
                    
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
                            field_result.found = True
                            content = label[field]
                            if isinstance(content, list):
                                content = " ".join(content)
                            
                            # Apply content length restriction if max_size is enabled
                            if max_size and max_content_length > 0 and len(content) > max_content_length:
                                original_length = len(content)
                                content = content[:max_content_length] + f"... [truncated, {original_length-max_content_length} more characters]"
                                field_result.truncated = True
                                field_result.original_length = original_length
                            
                            field_result.content = content
                            field_result.search_strategy = f"_exists_ search: {field}"
                            
                            # Extract NDC if available
                            if "openfda" in label and "product_ndc" in label["openfda"] and label["openfda"]["product_ndc"]:
                                field_result.ndc = label["openfda"]["product_ndc"][0]
                                all_ndcs_tried.add(field_result.ndc)
                                field_result.ndcs_tried.append(field_result.ndc)
                            
                            # Extract drug name if better than what we have
                            if "openfda" in label and "brand_name" in label["openfda"] and label["openfda"]["brand_name"]:
                                drug_name = label["openfda"]["brand_name"][0]
                            
                            # Get all sections from this label
                            field_result.all_sections = extract_all_sections(label)
                            field_result.message = f"Found {field} using last-ditch _exists_ search"
                except Exception as e:
                    logger.warning(f"Last-ditch search failed for field {field}: {str(e)}")
            
            # If still not found, add field result with failure info
            if not field_result.found:
                field_result.message = f"Field {field} not found after trying {len(field_result.ndcs_tried)} NDCs"
            
            # Add result for this field
            field_results.append(field_result)
        
        # Track search strategies used
        search_strategies_used = list(set(result.search_strategy for result in field_results if result.search_strategy))
        
        # Convert all_ndcs_tried set to sorted list
        all_ndcs_list = sorted(list(all_ndcs_tried))
        
        # Build the final response
        found_count = sum(1 for result in field_results if result.found)
        total_ndcs = len(all_ndcs_list)
        
        message = (
            f"Found {found_count} out of {len(requested_fields)} requested fields. "
            f"Tried {total_ndcs} NDCs across {len(search_strategies_used)} search strategies."
        )
        
        # For rate limits, add a note if we had API errors
        if any("error" in (result.message or "").lower() for result in field_results):
            message += " Some searches hit rate limits or API errors. Consider adding an FDA_API_KEY for higher limits."
        
        drug_name = name if name else "Unknown drug"
        if field_results and field_results[0].found and field_results[0].all_sections:
            # Try to extract a better drug name from the found data if possible
            for section in field_results[0].all_sections:
                if section.metadata and "openfda" in section.metadata:
                    openfda = section.metadata["openfda"]
                    if "brand_name" in openfda and openfda["brand_name"]:
                        drug_name = openfda["brand_name"][0]
                        break
                        
        # Add size optimization metadata
        metadata = {}
        truncated_fields = []
        total_characters_saved = 0
        size_optimization_applied = max_size and max_content_length > 0
        
        # Calculate total character savings and collect truncated field names
        if size_optimization_applied:
            for field_result in field_results:
                if field_result.truncated and field_result.original_length is not None:
                    truncated_fields.append(field_result.field)
                    characters_saved = field_result.original_length - len(field_result.content)
                    total_characters_saved += characters_saved
        
        # Add warning about truncation to the message if fields were truncated
        if truncated_fields:
            if message:
                message += f" {len(truncated_fields)} fields were truncated to limit response size."
            else:
                message = f"{len(truncated_fields)} fields were truncated to limit response size."
        
        # Create size optimization metadata
        if size_optimization_applied:
            metadata["size_optimization"] = {
                "applied": True,
                "max_content_length": max_content_length,
                "truncated_fields": truncated_fields,
                "total_characters_saved": total_characters_saved
            }
        
        # Add parameter metadata
        metadata["query_parameters"] = {
            "name": name,
            "ndc": ndc,
            "fields": fields,
            "ndc_limit": ndc_limit, 
            "last_ditch": last_ditch,
            "max_content_length": max_content_length,
            "max_size": max_size,
            "include_metadata": include_metadata
        }
        
        # Remove metadata from sections if not requested
        if not include_metadata:
            for field_result in field_results:
                field_result.all_sections = []
        
        return LLMLabelDiscoverResponse(
            success=found_count > 0,
            drug_name=drug_name,
            fields=field_results,
            message=message,
            all_ndcs_tried=all_ndcs_list,
            available_fields=available_fields,
            search_strategies_used=search_strategies_used,
            metadata=metadata
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in LLM label discover: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving label data: {str(e)}")

