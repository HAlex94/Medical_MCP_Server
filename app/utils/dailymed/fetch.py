"""
DailyMed Fetch Module

Provides functions for fetching drug data from DailyMed.
"""

import logging
from typing import Dict, Any, Optional

from bs4 import BeautifulSoup
import requests

from app.utils.dailymed.session import create_session, rate_limited, get_from_cache_or_fetch
from app.utils.dailymed.search import search_dailymed
from app.utils.dailymed.parse import extract_basic_info, extract_full_sections, extract_tables
from app.utils.dailymed.models import DrugData, DrugError

# Setup logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEOUT = 10  # seconds


@rate_limited
def get_soup_from_url(url: str) -> Optional[BeautifulSoup]:
    """
    Get BeautifulSoup object from a URL with rate limiting and security measures.
    
    Args:
        url: URL to fetch HTML from
        
    Returns:
        BeautifulSoup object or None if error
    """
    try:
        session = create_session()
        response = session.get(url, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except requests.RequestException as e:
        logger.error(f"Error fetching URL {url}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching URL {url}: {str(e)}")
        return None


@rate_limited
def get_drug_data(url: str) -> DrugData:
    """
    Retrieve detailed drug information from a DailyMed URL with rate limiting and caching.
    
    Args:
        url: DailyMed URL for the drug
        
    Returns:
        DrugData object with drug information
    """
    try:
        logger.info(f"Retrieving drug data from DailyMed: {url}")
        
        # Define a function to fetch the data that we can cache
        def fetch_drug_data():
            # Use rate-limited soup function
            soup = get_soup_from_url(url)
            if not soup:
                logger.error(f"Failed to retrieve content from URL: {url}")
                return DrugError(error=f"Failed to retrieve content from URL: {url}", url=url)
            
            # Extract basic info
            try:
                basic_info = extract_basic_info(soup)
            except Exception as e:
                logger.error(f"Error extracting basic info: {str(e)}")
                basic_info = {}
            
            # Extract sections
            try:
                sections = extract_full_sections(soup)
            except Exception as e:
                logger.error(f"Error extracting sections: {str(e)}")
                sections = {}
            
            # Extract tables
            try:
                tables = extract_tables(soup)
            except Exception as e:
                logger.error(f"Error extracting tables: {str(e)}")
                tables = {}
            
            # Create DrugData object
            drug_data = DrugData(
                title=basic_info.get('title'),
                manufacturer=basic_info.get('manufacturer'),
                active_ingredients=basic_info.get('active_ingredients', []),
                drug_class=basic_info.get('drug_class'),
                full_sections=sections,
                tables=tables,
                downloads=basic_info.get('downloads', {}),
                set_id=basic_info.get('set_id'),
                ndc_codes=basic_info.get('ndc_codes', [])
            )
            
            return drug_data
        
        return get_from_cache_or_fetch(url, fetch_drug_data)
    except Exception as e:
        logger.error(f"Error retrieving drug data: {str(e)}")
        return DrugError(error=f"Error retrieving drug data: {str(e)}", url=url)


@rate_limited
def get_drug_by_name(drug_name: str) -> DrugData:
    """
    High-level function to search for a drug and retrieve its data with rate limiting.
    
    Args:
        drug_name: Name of the drug to search for
        
    Returns:
        DrugData object or DrugError if not found
    """
    try:
        logger.info(f"Getting drug data for: {drug_name}")
        
        cache_key = f"drug_by_name_{drug_name}"
        
        def fetch_drug_by_name():
            # Search for drug
            search_results = search_dailymed(drug_name)
            
            if not search_results:
                logger.warning(f"No search results found for drug: {drug_name}")
                return DrugError(error="No results found", query=drug_name)
            
            # Get first result
            first_result = search_results[0]
            url = first_result.url
            
            # Get drug data
            drug_data = get_drug_data(url)
            
            # Add search metadata
            if not isinstance(drug_data, DrugError):
                drug_data.search_metadata = {
                    "query": drug_name,
                    "results_count": len(search_results),
                    "set_id": first_result.set_id,
                    "manufacturer": first_result.manufacturer,
                    "application_no": first_result.application_no
                }
            
            return drug_data
        
        return get_from_cache_or_fetch(cache_key, fetch_drug_by_name)
    except Exception as e:
        logger.error(f"Error getting drug by name: {str(e)}")
        return DrugError(error=f"Error getting drug by name: {str(e)}", query=drug_name)
