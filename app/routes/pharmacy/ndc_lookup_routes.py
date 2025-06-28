"""
NDC Lookup Routes

Endpoints for looking up drug product NDCs by drug name
to support ChatGPT's drug query workflow.
"""
from typing import List, Dict, Any, Optional
import logging
from fastapi import APIRouter, Query, HTTPException

from app.routes.fda.deprecated.label_info_routes import lookup_ndcs_for_name

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/ndc_lookup")
async def lookup_drug_ndcs(
    drug_name: str = Query(..., description="Drug name to lookup NDCs for"),
    limit: int = Query(10, description="Maximum number of NDCs to return")
):
    """
    Look up NDCs for a given drug name.
    
    This endpoint is specifically designed to support ChatGPT's two-step drug information workflow:
    1. First lookup NDCs for a drug name
    2. Then query label endpoints using those NDCs
    
    Returns a list of product entries with their NDCs.
    """
    if not drug_name:
        raise HTTPException(status_code=400, detail="Drug name is required")
        
    try:
        # Reuse our existing NDC lookup implementation
        products = await lookup_ndcs_for_name(drug_name, limit)
        
        if not products:
            logger.warning(f"No NDCs found for drug name: {drug_name}")
            return []
            
        logger.info(f"Found {len(products)} NDCs for drug {drug_name}")
        return products
        
    except Exception as e:
        logger.error(f"Error looking up NDCs for {drug_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to lookup NDCs: {str(e)}")
