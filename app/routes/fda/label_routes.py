"""
FDA Label Data Routes
Endpoints for retrieving structured FDA label data for drugs
"""
from fastapi import APIRouter, HTTPException, Query
import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging

from app.utils.api_clients import make_request

router = APIRouter()
logger = logging.getLogger(__name__)

class LabelDataField(BaseModel):
    """Model for a specific label data field with its values"""
    field_name: str
    values: List[str]

class LabelDataResponse(BaseModel):
    """Response model for label data"""
    drug_name: str
    fields: List[LabelDataField]
    openfda_data: Dict[str, Any] = {}  # Additional OpenFDA data

@router.get("/label/search", response_model=LabelDataResponse)
async def search_label_data(
    name: str = Query(..., description="Drug name (brand or generic)"),
    fields: Optional[str] = Query(None, description="Comma-separated list of label fields to return. If not specified, returns all available fields.")
):
    """
    Retrieve detailed label data for a drug by name.
    
    Parameters:
    - name: Drug name to search for (brand or generic name)
    - fields: Optional comma-separated list of specific fields to include (e.g., indications_and_usage,warnings,active_ingredient)
    
    Returns:
    - Label data for the drug with requested fields
    """
    try:
        # Add diagnostic logging to identify permission issue
        logger.info("Starting FDA label search with debugging enabled")
        
        # Log environment information
        logger.info(f"Environment variables: RENDER={os.environ.get('RENDER', 'Not set')}")
        logger.info(f"Cache settings: CACHE_ENABLED={os.environ.get('ENABLE_API_CACHE', 'Not explicitly set')}")
        logger.info(f"API_CACHE_DIR={os.environ.get('API_CACHE_DIR', 'Not explicitly set')}")
        
        # Log directory access attempts
        for test_dir in ["/tmp", "/var", "/var/data"]:
            try:
                if os.path.exists(test_dir):
                    logger.info(f"Directory {test_dir} exists")
                    # Check if writable
                    try:
                        test_file = os.path.join(test_dir, "test_write_permission.tmp")
                        with open(test_file, "w") as f:
                            f.write("test")
                        os.remove(test_file)
                        logger.info(f"Directory {test_dir} is writable")
                    except Exception as e:
                        logger.info(f"Directory {test_dir} is not writable: {e}")
                else:
                    logger.info(f"Directory {test_dir} does not exist")
            except Exception as e:
                logger.info(f"Error checking directory {test_dir}: {e}")
        
        # Format the search query to match FDA API requirements
        # Make the search more robust by normalizing the drug name and using a more flexible search
        # This handles edge cases and variations in drug names
        normalized_name = name.strip().lower()
        # Use parentheses to properly group search terms and ensure we catch all variants
        search_query = f"(openfda.generic_name:\"{normalized_name}\"~2+openfda.brand_name:\"{normalized_name}\"~2)"
        
        # FDA API endpoint for drug label search
        url = f"https://api.fda.gov/drug/label.json"
        params = {
            "search": search_query,
            "limit": 1  # Just need one good match
        }
        
        # Try to get the API key from environment if available
        from app.utils.api_clients import get_api_key
        api_key = get_api_key("FDA_API_KEY")
        if api_key:
            params["api_key"] = api_key
            logger.info("Using FDA API key for label search")
        else:
            logger.info("No FDA API key found, proceeding with unauthenticated request")
        
        logger.info(f"Searching FDA label database for: {name}")
        result = await make_request(url, params=params)
        
        if not result or "results" not in result or not result["results"]:
            logger.warning(f"No label data found with primary search, trying fallback search for: {name}")
            
            # Try a fallback search with just the active substance name
            # This is useful for generic drugs that may be listed under different names
            fallback_query = f"openfda.substance_name:\"{normalized_name}\"~2"
            fallback_params = {
                "search": fallback_query,
                "limit": 1
            }
            
            # Include API key if available
            if api_key:
                fallback_params["api_key"] = api_key
                
            logger.info(f"Attempting fallback search with substance name for: {name}")
            result = await make_request(url, params=fallback_params)
            
            if not result or "results" not in result or not result["results"]:
                logger.warning(f"No label data found for drug after fallback search: {name}")
                raise HTTPException(status_code=404, detail=f"No label data found for drug: {name}. Please check the drug name and try again.")
        
        # Get the first result (most relevant)
        label_data = result["results"][0]
        
        # Process fields to return
        requested_fields = []
        if fields:
            requested_fields = [field.strip() for field in fields.split(",")]
        
        # Collect the requested fields or all available fields
        response_fields = []
        
        # Determine which fields to include
        field_names_to_include = requested_fields if requested_fields else [
            key for key in label_data.keys() if key != "openfda"
        ]
        
        # Add each requested field if available
        for field_name in field_names_to_include:
            if field_name in label_data:
                response_fields.append(
                    LabelDataField(
                        field_name=field_name,
                        values=label_data[field_name]
                    )
                )
        
        # Include basic openfda data if available
        openfda_data = {}
        if "openfda" in label_data:
            # Extract useful openfda fields
            useful_openfda_fields = ["brand_name", "generic_name", "manufacturer_name", 
                                    "product_type", "route", "substance_name"]
            
            for field in useful_openfda_fields:
                if field in label_data["openfda"]:
                    openfda_data[field] = label_data["openfda"][field]
        
        return LabelDataResponse(
            drug_name=name,
            fields=response_fields,
            openfda_data=openfda_data
        )
        
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        logger.error(f"Error retrieving label data for {name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving label data: {str(e)}")
