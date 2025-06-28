#!/usr/bin/env python3
"""
Simplified FDA API Routes

FastAPI routes for the optimized FDA API client with 100% success rate.
Uses direct name-based queries to provide reliable drug label information.

Version 1.0.0 (2025-06-28)
"""

from fastapi import APIRouter, Query, Path, HTTPException
from typing import Dict, List, Optional, Any
import math
import time
from app.routes.fda.v3.fda_client import get_drug_label_info, IMPORTANT_FIELDS, TOKEN_RATIO

router = APIRouter(
    prefix="/v3",
    tags=["FDA API"],
    responses={
        404: {"description": "Drug information not found"},
        500: {"description": "FDA API error"}
    },
)

@router.get("/label-info")
async def get_simplified_label_info(
    name: str = Query(..., description="Generic or brand name of the drug"),
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to retrieve (e.g., indications_and_usage,warnings)"),
    optimize_for_llm: bool = Query(True, description="Apply LLM optimizations like truncation and token estimation"),
    max_content_length: int = Query(10000, description="Maximum content length before truncation (only used if optimize_for_llm=True)"),
) -> Dict[str, Any]:
    """
    Get label information for a drug using optimized FDA API client.
    
    Uses direct name-based queries with 100% success rate across top 50 drugs.
    This endpoint handles both simple drug names and compound formulations.
    
    The output is specifically optimized for LLM consumption with features like content
    truncation, token estimation, and field metadata to help handle long content.
    
    Args:
        name: Generic or brand name of the drug (e.g., "metformin" or "hydrocodone-acetaminophen")
        fields: Comma-separated list of fields to retrieve (leave blank for all standard fields)
        optimize_for_llm: Whether to apply LLM optimizations (truncation, token counting)
        max_content_length: Maximum length for field content before truncation
        
    Returns:
        Dictionary with all found fields and detailed metadata
    """
    start_time = time.time()
    field_list = fields.split(",") if fields else None
    
    # Get label info with LLM optimizations
    result = get_drug_label_info(
        drug_name=name, 
        fields=field_list,
        optimize_for_llm=optimize_for_llm,
        max_content_length=max_content_length
    )
    
    # Add timing information
    result['metadata']['total_time_ms'] = int((time.time() - start_time) * 1000)
    return result

@router.get("/label-info/{field_name}")
async def get_field_from_label(
    name: str = Query(..., description="Generic or brand name of the drug"),
    field_name: str = Path(..., description="Specific field to retrieve from the drug label"),
    optimize_for_llm: bool = Query(True, description="Apply LLM optimizations like truncation and token estimation"),
    max_content_length: int = Query(15000, description="Maximum content length before truncation (higher for single field endpoint)")
) -> Dict[str, Any]:
    """
    Get a single specific field from a drug label.
    
    Optimized endpoint for retrieving just one field like indications_and_usage or boxed_warning.
    Useful for LLMs that need focused access to specific label sections.
    
    This endpoint uses a higher default max_content_length since it only returns one field.
    For multi-field requests, use the standard /label-info endpoint.
    
    Args:
        name: Generic or brand name of the drug
        field_name: Specific label field to retrieve
        optimize_for_llm: Whether to apply LLM optimizations (truncation, token counting)
        max_content_length: Maximum content length before truncation
        
    Returns:
        Dictionary with the requested field and metadata, optimized for LLM consumption
    """
    result = get_drug_label_info(
        drug_name=name, 
        fields=[field_name],
        optimize_for_llm=optimize_for_llm,
        max_content_length=max_content_length
    )
    
    # Prepare response with additional LLM-friendly information
    response = {
        "drug_name": name,
        "field": field_name,
        "success": field_name in result,
        "metadata": {}
    }
    
    # Include only relevant metadata
    response["metadata"] = {
        "ndcs": result["metadata"].get("ndcs", []),
        "query_time_ms": result["metadata"].get("response_time_ms", 0),
        "brand_name": result["metadata"].get("brand_name", []),
        "generic_name": result["metadata"].get("generic_name", []),
    }
    
    # Add LLM optimization data if available
    if "llm_optimization" in result["metadata"]:
        response["metadata"]["llm_optimization"] = result["metadata"]["llm_optimization"]
    
    # Add field-specific metadata if truncated
    field_meta_key = f"{field_name}_metadata"
    if field_meta_key in result:
        response["metadata"]["content_metadata"] = result[field_meta_key]
    
    # Add content if found
    if result['success'] and field_name in result:
        response["content"] = result[field_name]
        
        # Add token estimation for the content
        if optimize_for_llm and isinstance(result[field_name], str):
            response["metadata"]["estimated_tokens"] = math.ceil(len(result[field_name]) / TOKEN_RATIO)
    else:
        response["content"] = None
        response["metadata"]["query_status"] = result["metadata"].get("query_status", "field_not_found")
    
    return response

@router.get("/available-fields")
async def list_available_fields() -> Dict[str, List[str]]:
    """
    Get a list of all available fields that can be requested in the label-info endpoint.
    
    Returns:
        Dictionary with list of standard fields and their variants
    """
    return {
        "standard_fields": IMPORTANT_FIELDS,
        "description": ["These fields can be requested in the /v3/label-info endpoint"]
    }
