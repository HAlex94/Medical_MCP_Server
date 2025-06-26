"""
FDA Label Information Routes

Specialized routes for retrieving comprehensive drug label information from FDA APIs,
designed for consistent LLM consumption with intelligent fallback mechanisms.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException
import httpx
import os
import logging
from pydantic import BaseModel
from app.utils.api_clients import make_request
from app.utils.shared import get_fda_api_key

router = APIRouter()
logger = logging.getLogger(__name__)

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

async def search_fda_label_with_fallbacks(
    name=None, 
    active_ingredient=None, 
    ndc=None, 
    limit=1
):
    """Search FDA label API with multiple fallback strategies"""
    # Implement intelligent query path selection
    search_queries = []
    
    # 1. Try exact name match if provided (least likely to work but most precise)
    if name:
        search_queries.append(f"openfda.brand_name.exact:\"{name}\"")
        search_queries.append(f"openfda.brand_name:\"{name}\"") 
        search_queries.append(f"brand_name:\"{name}\"")
    
    # 2. Try active ingredient if provided
    if active_ingredient:
        search_queries.append(f"openfda.generic_name.exact:\"{active_ingredient}\"")
        search_queries.append(f"openfda.generic_name:\"{active_ingredient}\"")
        search_queries.append(f"openfda.substance_name:\"{active_ingredient}\"")
    
    # 3. Try NDC if provided (most reliable when available)
    if ndc:
        search_queries.append(f"openfda.product_ndc.exact:\"{ndc}\"") 
        search_queries.append(f"openfda.product_ndc:\"{ndc}\"")
        search_queries.append(f"product_ndc:\"{ndc}\"")
    
    # If we have a name but no active ingredient or NDC, try partial matches
    if name and not (active_ingredient or ndc):
        search_queries.append(f"openfda.brand_name:{name}")
    
    # Make queries in order until we get a valid result
    for search_query in search_queries:
        try:
            url = f"https://api.fda.gov/drug/label.json?search={search_query}&limit={limit}"
            api_key = get_fda_api_key()
            if api_key:
                url += f"&api_key={api_key}"
                
            response = await make_request(url)
            
            # If we got results, return them
            if response and "results" in response and len(response["results"]) > 0:
                return response
                
        except Exception as e:
            logger.debug(f"Query failed: {search_query}. Error: {str(e)}")
            continue
    
    # If all queries failed, return None
    return None

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
        # Search FDA label API with fallbacks
        label_response = await search_fda_label_with_fallbacks(name, active_ingredient, ndc)
        
        if not label_response or "results" not in label_response or not label_response["results"]:
            raise HTTPException(status_code=404, detail="No drug label information found for the provided parameters")
            
        # Get the first label result (most relevant)
        label_data = label_response["results"][0]
        
        # Extract openfda metadata if available
        openfda = label_data.get("openfda", {})
        
        # Extract important sections
        sections = extract_label_sections(label_data)
        
        # Create response
        response = DrugLabelResponse(
            brand_name=openfda.get("brand_name", [name])[0] if openfda.get("brand_name") else name,
            generic_name=openfda.get("generic_name", [active_ingredient])[0] if openfda.get("generic_name") else active_ingredient,
            manufacturer=openfda.get("manufacturer_name", ["Unknown"])[0] if openfda.get("manufacturer_name") else None,
            ndc=openfda.get("product_ndc", [ndc]) if openfda.get("product_ndc") else ([ndc] if ndc else None),
            sections=sections,
            dosage_forms=openfda.get("dosage_form") if openfda.get("dosage_form") else None,
            route=openfda.get("route") if openfda.get("route") else None,
            application_numbers=openfda.get("application_number") if openfda.get("application_number") else None,
        )
        
        # Add message if no sections found
        if not sections:
            response.message = "Found drug label but no label sections were available"
            
        return response
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error getting drug label information: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving drug label information: {str(e)}")
