"""app/routes/fda/dailymed_routes.py — DailyMed fallback endpoints for drug information when OpenFDA is unavailable"""

from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Query, HTTPException, Path
from pydantic import BaseModel
import logging

from app.utils.dailymed_client import (
    search_dailymed,
    get_spl_data,
    find_drug_info_with_dailymed
)

router = APIRouter()
logger = logging.getLogger("app.routes.fda.dailymed")


# Models for API responses
class DailyMedSearchResult(BaseModel):
    """Search result from DailyMed API"""
    setid: str
    title: str
    spl_version: int
    publication_date: Optional[str] = None
    marketing_category_code: Optional[str] = None
    active_ingredient: Optional[str] = None
    source: str = "dailymed"
    
    class Config:
        schema_extra = {
            "example": {
                "setid": "1f748a60-746f-4879-a58c-3b1fd3f5fc4a",
                "title": "ATORVASTATIN CALCIUM Tablet",
                "spl_version": 3,
                "publication_date": "2019-11-15",
                "marketing_category_code": "ANDA",
                "active_ingredient": "ATORVASTATIN CALCIUM",
                "source": "dailymed"
            }
        }


class DailyMedDrugInfo(BaseModel):
    """Structured drug information from DailyMed"""
    source: str = "dailymed"
    setid: str
    brand_name: Optional[str] = None
    generic_name: Optional[str] = None
    indications: Optional[str] = None
    dosage: Optional[str] = None
    warnings: Optional[str] = None
    contraindications: Optional[str] = None
    adverse_reactions: Optional[str] = None
    drug_interactions: Optional[str] = None
    url: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "source": "dailymed",
                "setid": "1f748a60-746f-4879-a58c-3b1fd3f5fc4a",
                "brand_name": "ATORVASTATIN CALCIUM",
                "generic_name": "ATORVASTATIN CALCIUM",
                "indications": "Atorvastatin is indicated to reduce the risk of...",
                "dosage": "The recommended starting dose is 10 or 20 mg once daily...",
                "warnings": "Liver Dysfunction: Persistent elevations in hepatic transaminases...",
                "contraindications": "Active liver disease, which may include unexplained persistent...",
                "adverse_reactions": "The most common adverse reactions (incidence ≥ 2%) were...",
                "drug_interactions": "Strong Inhibitors of CYP 3A4: Atorvastatin is metabolized by...",
                "url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=1f748a60-746f-4879-a58c-3b1fd3f5fc4a"
            }
        }


@router.get("/dailymed-fallback", 
    response_model=List[DailyMedSearchResult],
    summary="Search DailyMed for drug information",
    description="Search the DailyMed database for drug information by name. "
               "This endpoint provides a fallback when FDA data is unavailable.")
async def dailymed_search(
    name: str = Query(..., description="Drug name to search for"),
    limit: int = Query(10, description="Maximum number of results to return")
) -> List[DailyMedSearchResult]:
    """
    Search for drug information in DailyMed by drug name.
    
    Args:
        name: Drug name to search for
        limit: Maximum number of results to return
    
    Returns:
        List of search results from DailyMed
    """
    if not name or len(name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Drug name is required")
    
    try:
        results = await search_dailymed(name, limit=limit)
        
        # Convert to DailyMedSearchResult format
        formatted_results = []
        for result in results:
            formatted_result = {
                "setid": result.get("setid", ""),
                "title": result.get("title", ""),
                "spl_version": result.get("spl_version", 0),
                "source": "dailymed"
            }
            
            # Add optional fields if present
            for field in ["publication_date", "marketing_category_code", "active_ingredient"]:
                if field in result:
                    formatted_result[field] = result[field]
                    
            formatted_results.append(DailyMedSearchResult(**formatted_result))
        
        return formatted_results
    
    except Exception as e:
        logger.error(f"Error during DailyMed search: {e}")
        raise HTTPException(status_code=500, detail=f"DailyMed search error: {str(e)}")


@router.get("/dailymed-fallback/spl/{setid}", 
    response_model=Dict[str, Any],
    summary="Get SPL data from DailyMed",
    description="Retrieve Structured Product Labeling (SPL) data for a drug from DailyMed using its setid.")
async def get_dailymed_spl(
    setid: str = Path(..., description="DailyMed setid for the drug")
) -> Dict[str, Any]:
    """
    Get Structured Product Labeling (SPL) data for a drug using its DailyMed setid.
    
    Args:
        setid: DailyMed setid for the drug
    
    Returns:
        SPL data for the drug
    """
    if not setid or len(setid.strip()) == 0:
        raise HTTPException(status_code=400, detail="Valid setid is required")
    
    try:
        spl_data = await get_spl_data(setid)
        
        if "error" in spl_data:
            raise HTTPException(status_code=404, detail=f"SPL data not found: {spl_data['error']}")
        
        return spl_data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving SPL data: {e}")
        raise HTTPException(status_code=500, detail=f"SPL data retrieval error: {str(e)}")


@router.get("/drug-search", 
    response_model=Dict[str, Any],
    summary="Search for drug information with fallback",
    description="Search for drug information using OpenFDA with DailyMed as a fallback when FDA data is unavailable.")
async def drug_search_with_fallback(
    name: str = Query(..., description="Drug name to search for"),
    use_fallback: bool = Query(True, description="Whether to use DailyMed as a fallback when FDA data is unavailable"),
    skip_openfda: bool = Query(False, description="Skip OpenFDA and only use DailyMed (for testing)")
) -> Dict[str, Any]:
    """
    Search for drug information with fallback to DailyMed when FDA data is unavailable.
    
    Args:
        name: Drug name to search for
        use_fallback: Whether to use DailyMed as a fallback
        skip_openfda: Skip OpenFDA and only use DailyMed (for testing)
    
    Returns:
        Combined drug information from OpenFDA and/or DailyMed
    """
    if not name or len(name.strip()) == 0:
        raise HTTPException(status_code=400, detail="Drug name is required")
    
    results = []
    sources_used = []
    
    try:
        # First try OpenFDA unless explicitly skipped
        openfda_found = False
        if not skip_openfda:
            # Import here to avoid circular import
            from app.routes.fda.ndc_routes import search_drug
            
            try:
                openfda_results = await search_drug(name)
                
                if openfda_results and len(openfda_results) > 0:
                    # Add source field to each result
                    for result in openfda_results:
                        result["source"] = "openfda"
                    
                    results.extend(openfda_results)
                    sources_used.append("openfda")
                    openfda_found = True
            
            except Exception as e:
                logger.warning(f"OpenFDA search failed, will use fallback: {e}")
        
        # Use DailyMed as fallback if needed
        if (not openfda_found and use_fallback) or skip_openfda:
            dailymed_results = await find_drug_info_with_dailymed(name)
            
            if dailymed_results and len(dailymed_results) > 0:
                results.extend(dailymed_results)
                sources_used.append("dailymed")
        
        return {
            "query": name,
            "results": results,
            "sources_used": sources_used,
            "total_results": len(results)
        }
    
    except Exception as e:
        logger.error(f"Error during drug search with fallback: {e}")
        raise HTTPException(status_code=500, detail=f"Drug search error: {str(e)}")
