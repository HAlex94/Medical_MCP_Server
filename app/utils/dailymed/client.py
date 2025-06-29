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
    
    async def search(self, drug_name: str, limit: int = 5) -> List[DrugResult]:
        logger.info(f"Searching for drug: {drug_name} (limit: {limit})")
        try:
            raw = await search_dailymed(drug_name, limit)
            return [DrugResult(**item) for item in raw]
        except Exception as e:
            logger.error(f"Error searching for {drug_name}: {e}")
            raise DrugError(error=str(e))
    
    async def get_drug_data(self, url: str) -> DrugData:
        logger.info(f"Getting drug data from URL: {url}")
        try:
            raw = await get_drug_data(url)
            if isinstance(raw, dict) and raw.get("error"):
                raise DrugError(error=raw["error"])
            return DrugData(**raw)
        except Exception as e:
            logger.error(f"Error fetching data from {url}: {e}")
            raise DrugError(error=str(e))
    
    async def get_drug_by_name(self, drug_name: str) -> DrugData:
        logger.info(f"Getting drug by name: {drug_name}")
        try:
            raw = await get_drug_by_name(drug_name)
            if hasattr(raw, "error") or (isinstance(raw, dict) and raw.get("error")):
                raise DrugError(error=raw.get("error", "Unknown error"))
            return DrugData(**raw)
        except Exception as e:
            logger.error(f"Error getting drug by name {drug_name}: {e}")
            raise DrugError(error=str(e))
