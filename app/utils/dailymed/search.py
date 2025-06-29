"""
DailyMed Search Module

Provides functions for searching DailyMed for drug information.
"""

import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.utils.dailymed.session import create_session, rate_limited, get_from_cache_or_fetch
from app.utils.dailymed.models import DrugResult

# Setup logging
logger = logging.getLogger(__name__)

# Constants
BASE_URL = 'https://dailymed.nlm.nih.gov'
SEARCH_URL = f"{BASE_URL}/dailymed/search.cfm"
DEFAULT_TIMEOUT = 10  # seconds


@rate_limited
def search_dailymed(drug_name: str, limit: int = 5) -> List[DrugResult]:
    """
    Search DailyMed for drug information with rate limiting and security measures.
    
    Args:
        drug_name: Name of the drug to search for
        limit: Maximum number of results to return
        
    Returns:
        List of search results with name and URL
    """
    try:
        params = {
            "labeltype": "human",
            "query": drug_name,
            "pagesize": limit,
            "page": 1,
            "sortby": "relevancy"
        }
        
        logger.info(f"Searching DailyMed for: {drug_name} with params: {params}")
        
        # Use our session with retry logic and user agent rotation
        session = create_session()
        
        # Use cache if available for search results
        cache_key = f"{SEARCH_URL}?{drug_name}_{limit}"
        
        def perform_search():
            try:
                # Make the request to DailyMed search
                response = session.get(SEARCH_URL, params=params, timeout=DEFAULT_TIMEOUT)
                response.raise_for_status()
                logger.info(f"DailyMed search response status: {response.status_code}")
                logger.info(f"DailyMed search URL: {response.url}")
                return response
            except Exception as e:
                logger.error(f"Error searching DailyMed for {drug_name}: {str(e)}")
                return None
        
        # Get response using cache mechanism
        response = get_from_cache_or_fetch(cache_key, perform_search)
        
        if response is None:
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
    
    except Exception as e:
        logger.error(f"Error searching DailyMed for {drug_name}: {str(e)}")
        return []
    
    results = []
    
    # Find drug links using multiple strategies
    logger.info(f"Response text length: {len(response.text) if response else 0} characters")
    
    # Strategy 1: Find all links that might be drug links
    all_links = soup.find_all('a')
    logger.info(f"Found {len(all_links)} total links")
    
    # Filter links to those that appear to be drug-related
    drug_links = []
    for link in all_links:
        href = link.get('href', '')
        # DailyMed drug URLs typically contain these patterns
        if any(pattern in href.lower() for pattern in ['setid=', 'druginfo', 'monograph', 'label', 'dailymed/lookup']):
            drug_links.append(link)
    
    logger.info(f"Found {len(drug_links)} potential drug links")
    
    # Process drug links to extract information
    for link in drug_links[:limit]:  # Limit to the requested number of results
        href = link.get('href', '')
        if not href:
            continue
            
        # Get the full URL
        url = urljoin(BASE_URL, href)
        
        # Extract drug name from link text or surroundings
        name = link.get_text(strip=True)
        if not name or len(name) < 2:  # Very short names are likely not drug names
            # Try to find name in parent element
            parent = link.parent
            if parent:
                name = parent.get_text(strip=True)
        
        # Use the search term if we couldn't find a good name
        if not name or len(name) < 2:
            name = drug_name
        
        # Extract the set ID from URL if present
        set_id = None
        if 'setid=' in url:
            set_id = url.split('setid=')[-1].split('&')[0]
        
        # Extract manufacturer information from surrounding elements
        manufacturer = None
        
        # Look for manufacturer in parent elements
        for parent in link.parents:
            if parent.name in ['div', 'li', 'tr', 'td', 'span', 'p']:
                parent_text = parent.get_text(strip=True)
                
                # Check for manufacturer indicators
                indicators = ['manufactured by', 'marketed by', 'distributed by', 
                              'packaged by', 'manufacturer', 'labeler', 'applicant',
                              'company', 'corporation', 'inc.', 'llc', 'pharmaceutical']
                              
                for indicator in indicators:
                    if indicator in parent_text.lower():
                        # Get text around the indicator
                        idx = parent_text.lower().find(indicator)
                        # Take a reasonable chunk around it
                        potential_manu = parent_text[max(0, idx-20):min(len(parent_text), idx+60)]
                        if potential_manu and 5 < len(potential_manu) < 100:
                            manufacturer = potential_manu
                            break
                
                if manufacturer:
                    break
        
        # Check for application number in URL
        appl_no = None
        if 'applno=' in url:
            appl_no = url.split('applno=')[-1].split('&')[0]
            
        # Add result to our list using the DrugResult dataclass
        results.append(DrugResult(
            drug_name=name,
            url=url,
            set_id=set_id,
            manufacturer=manufacturer,
            application_no=appl_no
        ))
    
    # If we didn't find any results but found drug links, add simple entries
    if not results and drug_links:
        for link in drug_links[:limit]:
            href = link.get('href', '')
            if href:
                url = urljoin(BASE_URL, href)
                results.append(DrugResult(
                    drug_name=drug_name,  # Use search term as fallback
                    url=url,
                    set_id=None,
                    manufacturer=None,
                    application_no=None
                ))
    
    logger.info(f"Found {len(results)} search results for {drug_name}")
    return results
