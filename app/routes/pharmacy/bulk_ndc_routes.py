"""
Bulk NDC Lookup Routes

Provides endpoints for retrieving comprehensive NDC data with multi-page results aggregation
to ensure complete coverage of all available NDCs for a given drug. Supports export in different formats.
"""
from typing import List, Dict, Any, Optional
import logging
import asyncio
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException, Response
from fastapi.responses import StreamingResponse, JSONResponse

from app.routes.fda.ndc_routes import search_ndc_compact
from app.utils.api_clients import make_api_request
from app.utils.formatters import json_to_csv, json_to_txt, ndc_products_to_simplified_format

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/bulk-ndc/search")
async def bulk_ndc_search(
    name: Optional[str] = None,
    active_ingredient: Optional[str] = None,
    manufacturer: Optional[str] = None,
    max_results: int = 1000,
    format: Optional[str] = None,  # Format option: csv, txt, or json (default)
    filename: Optional[str] = None  # Optional custom filename for downloads
):
    """
    Comprehensive NDC search that retrieves multiple pages of results and aggregates them.
    
    This endpoint is specifically designed for bulk data retrieval when all NDCs for a medication
    are needed, such as for CSV exports or comprehensive medication analysis.
    
    Parameters:
    - name: Brand or generic name of the drug
    - active_ingredient: Active ingredient in the drug
    - manufacturer: Name of the manufacturer
    - max_results: Maximum number of total results to return (default: 1000)
    - format: Output format (json, csv, txt). If specified, returns downloadable file
    - filename: Custom filename for the download (without extension)
    
    Returns:
    - If format is None: JSON response with product data
    - If format is specified: Downloadable file in the requested format
    """
    if not (name or active_ingredient or manufacturer):
        raise HTTPException(status_code=400, detail="At least one search parameter is required")
        
    try:
        all_products = []
        page_size = 100  # FDA API maximum page size
        skip = 0
        more_results = True
        
        logger.info(f"Starting bulk NDC search for {name or active_ingredient or manufacturer}")
        
        # Continue fetching pages until we either reach max_results or there are no more results
        while more_results and len(all_products) < max_results:
            # Use the existing search_ndc_compact function but access it directly to avoid API validation
            page_results = await search_ndc_compact(
                name=name,
                active_ingredient=active_ingredient, 
                manufacturer=manufacturer,
                limit=page_size,
                skip=skip
            )
            
            if not page_results.products or len(page_results.products) == 0:
                more_results = False
                logger.info(f"No more results found after retrieving {len(all_products)} products")
            else:
                all_products.extend(page_results.products)
                logger.info(f"Retrieved page with {len(page_results.products)} products, total so far: {len(all_products)}")
                skip += page_size
            
            # Avoid overwhelming the API with rapid requests
            await asyncio.sleep(0.5)
        
        # Calculate the actual total results if we have a complete set
        total_results = page_results.total_results if not more_results else max(len(all_products), page_results.total_results)
        
        logger.info(f"Bulk NDC search complete. Retrieved {len(all_products)} products out of total {total_results}")
        
        # Limit products to max_results
        products_to_return = all_products[:max_results]
        
        # Prepare response based on requested format
        if format and format.lower() in ['csv', 'txt']:
            # Generate a default filename if none provided
            if not filename:
                search_term = name or active_ingredient or manufacturer or "all"
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"ndc_data_{search_term}_{timestamp}"
            
            # Convert to simplified format for better export
            simplified_products = ndc_products_to_simplified_format(products_to_return)
            
            if format.lower() == 'csv':
                # Generate CSV content
                content = json_to_csv(simplified_products)
                media_type = "text/csv"
                filename = f"{filename}.csv"
                
            elif format.lower() == 'txt':
                # Generate TXT content
                content = json_to_txt(simplified_products)
                media_type = "text/plain"
                filename = f"{filename}.txt"
            
            # Return as downloadable file
            headers = {
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
            return Response(content=content, media_type=media_type, headers=headers)
            
        else:  # Default JSON response
            # Return standard JSON response
            return {
                "query": f"name={name} ingredient={active_ingredient} manufacturer={manufacturer}",
                "total_results": total_results,
                "displayed_results": len(products_to_return),
                "products": products_to_return,
                "complete": not more_results  # Flag to indicate if we retrieved all available results
            }
        
    except Exception as e:
        logger.error(f"Error in bulk NDC search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to complete bulk NDC search: {str(e)}")
