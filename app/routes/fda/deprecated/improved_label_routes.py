"""
Improved FDA Label Routes

This module provides optimized FastAPI endpoints for FDA drug label queries,
implementing PillQ's proven strategies for higher success rates.
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .improved_fda_client import get_drug_label_info, lookup_ndcs_for_name
import logging

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Models for API responses
class LabelField(BaseModel):
    name: str
    content: str

class LabelMetadata(BaseModel):
    source_ndc: str
    field_length: int

class ImprovedLabelResponse(BaseModel):
    drug_name: str = Field(description="Drug name queried")
    success: bool = Field(description="Whether any label fields were found")
    fields: List[LabelField] = Field(default_factory=list, description="List of label fields found")
    ndcs_tried: List[str] = Field(default_factory=list, description="NDCs that were tried")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata about the query and results")

@router.get("/v2/label-info", response_model=ImprovedLabelResponse)
async def get_improved_label_info(
    name: Optional[str] = Query(None, description="Brand or generic name of the drug"),
    ndc: Optional[str] = Query(None, description="NDC code of the drug"),
    fields: Optional[str] = Query(None, description="Comma-separated list of label fields to retrieve")
):
    """
    Get comprehensive drug label information using optimized PillQ strategy.
    
    This endpoint implements several improvements:
    1. Proper NDC normalization (package-level to product-level)
    2. Checking both top-level and openfda sub-objects for fields
    3. Multiple fallback strategies with proper FDA API query format
    4. Detailed metadata about which NDCs provided which information
    """
    if not name and not ndc:
        raise HTTPException(status_code=400, detail="Either 'name' or 'ndc' parameter is required")
    
    # Parse requested fields
    requested_fields = None
    if fields:
        requested_fields = [f.strip() for f in fields.split(",")]
    
    # Use our improved client to get label information
    result = get_drug_label_info(drug_name=name, ndc=ndc, fields=requested_fields)
    
    # Convert the result to our response model format
    response = ImprovedLabelResponse(
        drug_name=name or "Unknown",
        success=result["success"],
        ndcs_tried=result["ndcs_tried"],
        metadata=result["metadata"]
    )
    
    # Add all found fields to the response
    for field in result["fields_found"]:
        field_value = result.get(field)
        if field_value:
            # Convert list fields to strings
            if isinstance(field_value, list):
                field_value = "\n".join(field_value)
            
            response.fields.append(LabelField(
                name=field,
                content=field_value
            ))
    
    if not response.success:
        logger.warning(f"No label information found for {name or ndc}")
    else:
        logger.info(f"Successfully found {len(response.fields)} fields for {name or ndc}")
    
    return response

@router.get("/v2/ndc-lookup", response_model=List[str])
async def improved_ndc_lookup(
    name: str = Query(..., description="Brand or generic name of the drug"),
    limit: int = Query(10, description="Maximum number of NDCs to return")
):
    """
    Lookup NDCs for a drug name using optimized FDA API query format.
    
    Returns a list of normalized product-level NDCs.
    """
    if not name:
        raise HTTPException(status_code=400, detail="Drug name is required")
    
    ndcs = lookup_ndcs_for_name(name, limit=limit)
    
    logger.info(f"Found {len(ndcs)} NDCs for drug name: {name}")
    return ndcs
