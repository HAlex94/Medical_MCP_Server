"""
FDA Drug Information API Module

This module provides functions to query the FDA's drug databases for information
on prescription and over-the-counter medications.
"""
import logging
from typing import Dict, Any, List
from app.utils.api_clients import make_request, get_api_key

logger = logging.getLogger(__name__)

# FDA API endpoints
FDA_API_BASE = "https://api.fda.gov/drug"
FDA_LABEL_ENDPOINT = f"{FDA_API_BASE}/label.json"
FDA_NDC_ENDPOINT = f"{FDA_API_BASE}/ndc.json"

async def search_medication(query: str, limit: int = 5) -> Dict[str, Any]:
    """
    Search for medication information in the FDA database.
    
    Args:
        query: Medication name or active ingredient
        limit: Maximum number of results to return
        
    Returns:
        Dictionary containing medication information
    """
    logger.info(f"Searching FDA database for: {query}")
    
    # Get FDA API key if available
    fda_api_key = get_api_key("FDA_API_KEY")
    
    try:
        # Build FDA API query
        # We search both the brand name and generic name fields
        search_query = f"(openfda.brand_name:{query}+openfda.generic_name:{query})"
        params = {
            "search": search_query,
            "limit": limit,
        }
        
        # Add API key to params if available (FDA accepts it as a parameter)
        if fda_api_key:
            params["api_key"] = fda_api_key
        
        # Make request to FDA API
        response = await make_request(
            url=FDA_LABEL_ENDPOINT,
            params=params,
            method="GET"
        )
        
        if not response or "results" not in response:
            return {
                "status": "error",
                "message": "No results found in FDA database",
                "query": query,
                "medications": []
            }
        
        # Process and extract relevant medication information
        medications = []
        for result in response.get("results", []):
            openfda = result.get("openfda", {})
            
            medication = {
                "brand_name": openfda.get("brand_name", ["Unknown"])[0],
                "generic_name": openfda.get("generic_name", ["Unknown"])[0],
                "manufacturer": openfda.get("manufacturer_name", ["Unknown"])[0],
                "route": openfda.get("route", ["Unknown"])[0],
                "indications_and_usage": result.get("indications_and_usage", ["No information available"])[0],
                "warnings": result.get("warnings", ["No warnings available"])[0],
                "dosage_and_administration": result.get("dosage_and_administration", ["No dosage information available"])[0],
                "drug_interactions": result.get("drug_interactions", ["No interaction information available"])[0],
            }
            medications.append(medication)
        
        return {
            "status": "success",
            "message": f"Found {len(medications)} medications matching '{query}'",
            "query": query,
            "medications": medications
        }
        
    except Exception as e:
        logger.error(f"Error searching FDA database: {e}")
        return {
            "status": "error",
            "message": f"Error searching FDA database: {str(e)}",
            "query": query,
            "medications": []
        }
