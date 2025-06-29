"""
DailyMed API Client Package

A modular package for interacting with DailyMed's website to retrieve drug information.
"""

from app.utils.dailymed.client import DailyMedClient
from app.utils.dailymed.models import DrugResult, DrugData, DrugError, Section
from app.utils.dailymed.search import search_dailymed
from app.utils.dailymed.fetch import get_drug_data, get_drug_by_name, get_soup_from_url

__all__ = [
    'DailyMedClient',
    'DrugResult',
    'DrugData',
    'DrugError',
    'Section',
    'search_dailymed',
    'get_drug_data',
    'get_drug_by_name',
    'get_soup_from_url',
]
