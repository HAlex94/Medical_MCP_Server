"""app/utils/dailymed_client.py — DailyMed API client for drug information fallback when OpenFDA data is unavailable"""

import logging
import json
from typing import Dict, List, Any, Optional
from urllib.parse import quote
import httpx
from bs4 import BeautifulSoup

import asyncio
from json import JSONDecodeError

from app.utils.dailymed.parse import assemble_drug_record

logger = logging.getLogger("app.utils.dailymed")

# Constants for DailyMed web scraping
DAILYMED_SEARCH_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
DAILYMED_HTML_BASE = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}"

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
        async with httpx.AsyncClient(timeout=10.0) as client:
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
    except JSONDecodeError as e:
        logger.error(f"JSON decode error during DailyMed search: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error during DailyMed search: {e}")
        return []

async def get_spl_data(setid: str) -> Dict[str, Any]:
    """
    Retrieve structured SPL data for a drug from DailyMed using its setid.
    
    Args:
        setid: The DailyMed setid for the drug
        
    Returns:
        Dictionary containing structured drug information
    """
    if not setid or len(setid.strip()) == 0:
        logger.warning("Empty setid provided for DailyMed SPL data")
        return {"error": "Invalid setid"}
    
    # Construct the URL for this setid
    url = DAILYMED_HTML_BASE.format(setid=setid)
    
    # Browser-like headers to avoid 415 errors
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://dailymed.nlm.nih.gov/dailymed/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0"
    }
    
    try:
        # Fetch the HTML content
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Delegate assembly to helper for JSON-friendly structure
            return assemble_drug_record(soup, url=url, setid=setid)
            
    except httpx.HTTPError as e:
        logger.error(f"HTTP error during DailyMed HTML scraping: {e}")
        return {"error": f"HTTP error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error during DailyMed HTML scraping: {e}", exc_info=True)
        return {"error": f"Error processing data: {str(e)}"}

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
    if not drug_name or len(drug_name.strip()) == 0:
        logger.warning("Empty drug name provided to DailyMed fallback")
        return []
    
    drug_name = drug_name.strip()
    logger.info(f"Finding drug info for '{drug_name}' using DailyMed fallback")
    
    try:
        # First search for the drug by name
        search_results = await search_dailymed(drug_name)
        if not search_results:
            logger.info(f"No DailyMed results found for '{drug_name}'")
            return []

        # Fetch detailed SPL data concurrently for the top 3 setids
        setids = [r["setid"] for r in search_results[:3] if r.get("setid")]
        tasks = [get_spl_data(sid) for sid in setids]
        spl_results = await asyncio.gather(*tasks)

        # Filter out any errors and return structured records
        return [res for res in spl_results if "error" not in res]
        
    except Exception as e:
        logger.error(f"Error in DailyMed fallback for '{drug_name}': {str(e)}", exc_info=True)
        return []
