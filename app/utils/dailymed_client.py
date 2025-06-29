"""app/utils/dailymed_client.py — DailyMed API client for drug information fallback when OpenFDA data is unavailable"""

import httpx
import logging
import re
import json
from typing import Dict, List, Optional, Any, Tuple
from bs4 import BeautifulSoup
import asyncio
from urllib.parse import quote

logger = logging.getLogger("app.utils.dailymed")

# Constants for DailyMed API
DAILYMED_SEARCH_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
DAILYMED_SPL_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.json"
DAILYMED_SECTIONS_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}/sections.json"
DAILYMED_HTML_BASE = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}"

# Common section names and their standardized keys
SECTION_NAME_MAPPING = {
    "indications & usage": "indications_and_usage",
    "indications and usage": "indications_and_usage",
    "dosage & administration": "dosage_and_administration",
    "dosage and administration": "dosage_and_administration",
    "contraindications": "contraindications",
    "warnings": "warnings",
    "warnings and precautions": "warnings",
    "adverse reactions": "adverse_reactions",
    "drug interactions": "drug_interactions",
    "clinical pharmacology": "clinical_pharmacology",
    "mechanism of action": "mechanism_of_action",
    "pharmacokinetics": "pharmacokinetics",
    "how supplied": "how_supplied",
    "description": "description",
    "active ingredient": "active_ingredient"
}

async def search_dailymed(drug_name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search DailyMed for drug information by name.
    
    Args:
        drug_name: The drug name to search for
        limit: Maximum number of results to return
        
    Returns:
        List of search results with metadata
    """
    if not drug_name or len(drug_name.strip()) == 0:
        logger.warning("Empty drug name provided for DailyMed search")
        return []
    
    # URL encode the drug name for the API request
    encoded_name = quote(drug_name.strip())
    search_url = f"{DAILYMED_SEARCH_URL}?drug_name={encoded_name}&page=1&pagesize={limit}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(search_url)
            response.raise_for_status()
            data = response.json()
            
            # Extract and return the search results
            if "data" in data and isinstance(data["data"], list):
                return data["data"]
            else:
                return []
                
    except httpx.HTTPError as e:
        logger.error(f"HTTP error during DailyMed search: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error during DailyMed search: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error during DailyMed search: {e}")
        return []

async def get_spl_data(setid: str) -> Dict[str, Any]:
    """
    Get Structured Product Labeling (SPL) data for a drug using its setid.
    
    Args:
        setid: The DailyMed setid for the drug
        
    Returns:
        Dictionary containing SPL data
    """
    if not setid or len(setid.strip()) == 0:
        return {"error": "Invalid setid provided"}
    
    try:
        # Get basic SPL metadata
        async with httpx.AsyncClient() as client:
            response = await client.get(DAILYMED_SPL_URL.format(setid=setid))
            response.raise_for_status()
            spl_metadata = response.json()
            
            # Get SPL section data
            sections_response = await client.get(DAILYMED_SECTIONS_URL.format(setid=setid))
            sections_response.raise_for_status()
            sections_data = sections_response.json()
        
        # Extract useful section content
        processed_data = {}
        if "data" in sections_data and isinstance(sections_data["data"], list):
            for section in sections_data["data"]:
                if "title" in section and "text" in section:
                    section_title = section["title"].lower()
                    
                    # Map to standardized section names
                    for key_pattern, normalized_key in SECTION_NAME_MAPPING.items():
                        if key_pattern in section_title:
                            # Simple HTML parsing to extract text
                            soup = BeautifulSoup(section["text"], 'html.parser')
                            processed_data[normalized_key] = soup.get_text(separator=' ', strip=True)
                            break
        
        # Extract drug names and other basic info from metadata
        result = {
            "setId": setid,
            "data": processed_data
        }
        
        if "data" in spl_metadata:
            # Add drug name, active ingredient, and other basic metadata if available
            for key in ["drug_name", "active_ingredient", "drug_class", "marketing_category"]:
                if key in spl_metadata["data"]:
                    result[key] = spl_metadata["data"][key]
        
        return result
        
    except httpx.HTTPError as e:
        logger.error(f"HTTP error during DailyMed SPL retrieval: {e}")
        return {"error": f"HTTP error: {str(e)}"}
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error during DailyMed SPL retrieval: {e}")
        return {"error": f"JSON decode error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error during DailyMed SPL retrieval: {e}")
        return {"error": f"Unexpected error: {str(e)}"}

async def find_drug_info_with_dailymed(drug_name: str) -> List[Dict[str, Any]]:
    """
    Find comprehensive drug information using DailyMed as a fallback source.
    This function searches for a drug and then retrieves detailed SPL data
    for the top match.
    
    Args:
        drug_name: Drug name to search for
        
    Returns:
        List of structured drug data from DailyMed
    """
    # First search for the drug to get setids
    search_results = await search_dailymed(drug_name, limit=5)
    
    if not search_results:
        return []
    
    # For each search result, get the detailed SPL data
    # We'll limit to top 3 results to avoid making too many requests
    tasks = []
    for result in search_results[:3]:
        if "setid" in result:
            tasks.append(get_spl_data(result["setid"]))
    
    if not tasks:
        return []
    
    # Fetch all SPL data in parallel
    spl_results = await asyncio.gather(*tasks)
    
    # Process and normalize the data for consistent access
    processed_results = []
    for result in spl_results:
        if "error" not in result:
            # Create a structured response with consistent field names
            processed_data = {
                "source": "dailymed",
                "setid": result.get("setId", ""),
                "brand_name": result.get("drug_name", ""),
                "generic_name": result.get("active_ingredient", ""),
                "indications": result.get("data", {}).get("indications_and_usage", ""),
                "dosage": result.get("data", {}).get("dosage_and_administration", ""),
                "warnings": result.get("data", {}).get("warnings", ""),
                "contraindications": result.get("data", {}).get("contraindications", ""),
                "adverse_reactions": result.get("data", {}).get("adverse_reactions", ""),
                "drug_interactions": result.get("data", {}).get("drug_interactions", ""),
                "url": DAILYMED_HTML_BASE.format(setid=result.get("setId", ""))
            }
            processed_results.append(processed_data)
    
    return processed_results
