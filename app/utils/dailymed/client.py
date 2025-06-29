"""
DailyMed Client

High-level interface for DailyMed operations.
"""

import logging
from typing import List, Dict, Any, Optional

from app.utils.dailymed.session import create_session
from app.utils.dailymed.search import search_dailymed
from app.utils.dailymed.fetch import get_drug_data, get_drug_by_name
from app.utils.dailymed.models import DrugResult, DrugData, DrugError

# Setup logging
logger = logging.getLogger(__name__)


class DailyMedClient:
    """High-level client for DailyMed operations."""
    
    def __init__(self):
        """Initialize the client with a session."""
        self.session = create_session()
    
    def search(self, drug_name: str, limit: int = 5) -> List[DrugResult]:
        """
        Search for drugs by name.
        
        Args:
            drug_name: Name of drug to search for
            limit: Maximum number of results to return
            
        Returns:
            List of search results
        """
        logger.info(f"Searching for drug: {drug_name} (limit: {limit})")
        return search_dailymed(drug_name, limit)
    
    def get_drug_data(self, url: str) -> DrugData:
        """
        Retrieve detailed drug information from a URL.
        
        Args:
            url: DailyMed URL for the drug
            
        Returns:
            Drug data object
        """
        logger.info(f"Getting drug data from URL: {url}")
        return get_drug_data(url)
    
    def get_drug_by_name(self, drug_name: str) -> DrugData:
        """
        High-level function to search and retrieve drug data.
        
        Args:
            drug_name: Name of the drug to search for
            
        Returns:
            Drug data object or error
        """
        logger.info(f"Getting drug by name: {drug_name}")
        return get_drug_by_name(drug_name)
    
    def extract_section(self, drug_data: DrugData, section_keywords: List[str], 
                       case_sensitive: bool = False) -> Optional[str]:
        """
        Extract a specific section from drug data based on keywords.
        
        Args:
            drug_data: Drug data object
            section_keywords: List of keywords to match in section titles
            case_sensitive: Whether to match case sensitively
            
        Returns:
            Section content if found, None otherwise
        """
        logger.info(f"Extracting section with keywords: {section_keywords}")
        
        if not drug_data or not hasattr(drug_data, 'full_sections'):
            return None
            
        for section_title, content in drug_data.full_sections.items():
            title_to_check = section_title if case_sensitive else section_title.lower()
            
            for keyword in section_keywords:
                keyword_to_check = keyword if case_sensitive else keyword.lower()
                
                if keyword_to_check in title_to_check:
                    logger.info(f"Found matching section: {section_title}")
                    return content
        
        logger.info("No matching section found")
        return None
    
    def extract_tables_from_section(self, drug_data: DrugData, section_keywords: List[str],
                                  case_sensitive: bool = False) -> List[List[Dict[str, str]]]:
        """
        Extract tables from a specific section based on keywords.
        
        Args:
            drug_data: Drug data object
            section_keywords: List of keywords to match in section titles
            case_sensitive: Whether to match case sensitively
            
        Returns:
            List of tables from matching sections
        """
        logger.info(f"Extracting tables from section with keywords: {section_keywords}")
        
        result_tables = []
        
        if not drug_data or not hasattr(drug_data, 'tables'):
            return result_tables
            
        for section_title, tables in drug_data.tables.items():
            title_to_check = section_title if case_sensitive else section_title.lower()
            
            for keyword in section_keywords:
                keyword_to_check = keyword if case_sensitive else keyword.lower()
                
                if keyword_to_check in title_to_check:
                    logger.info(f"Found matching tables in section: {section_title}")
                    result_tables.extend(tables)
        
        logger.info(f"Found {len(result_tables)} matching tables")
        return result_tables
