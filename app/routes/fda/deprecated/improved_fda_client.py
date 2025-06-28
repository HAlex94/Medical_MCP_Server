#!/usr/bin/env python3
"""
Improved FDA API Client

This module implements optimized FDA API queries based on proven strategies from PillQ
to ensure maximum success rates for drug label data retrieval.
"""

import logging
import urllib.parse
from typing import Dict, List, Optional, Any, Union
import requests
import os

# Configure logging
logger = logging.getLogger(__name__)

# Constants
FDA_LABEL_API_URL = "https://api.fda.gov/drug/label.json"
FDA_NDC_API_URL = "https://api.fda.gov/drug/ndc.json"

# Common field mappings
IMPORTANT_FIELDS = [
    "active_ingredient",
    "inactive_ingredient",
    "indications_and_usage",
    "boxed_warning",
    "warnings",
    "warnings_and_cautions",
    "warnings_and_precautions", 
    "adverse_reactions",
    "dosage_and_administration",
    "contraindications",
    "drug_interactions",
    "pregnancy",
]

def get_api_key() -> str:
    """Get FDA API key from environment variable"""
    return os.environ.get("FDA_API_KEY", "")

def normalize_ndc(ndc: str) -> str:
    """
    Normalize NDC format for FDA API queries.
    1. Remove hyphens
    2. Convert package-level NDCs (e.g., 12345-6789-0) to product-level NDCs (12345-6789)
    3. Handle different formats (4-4-2, 5-3-2, 5-4-1, etc.)
    """
    if not ndc:
        return ""
        
    # Remove all hyphens for clean version
    clean_ndc = ndc.replace("-", "")
    
    # Convert package-level NDC (with 3 segments) to product-level NDC (with 2 segments)
    parts = ndc.split("-")
    if len(parts) == 3:  # This is likely a package-level NDC
        # Recreate as product-level NDC (first two segments)
        product_ndc = f"{parts[0]}-{parts[1]}"
        # Also return clean version without hyphens
        clean_ndc = product_ndc.replace("-", "")
        logger.debug(f"Normalized package NDC '{ndc}' to product NDC '{product_ndc}' (clean: {clean_ndc})")
    
    return clean_ndc

def get_field_from_openfda(ndc: str = None, field_key: str = None, drug_name: str = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve a specific field from openFDA label API.
    
    Implements PillQ's successful strategy to check both top-level and openfda sub-object,
    with fallbacks from NDC to generic_name and brand_name.
    
    Args:
        ndc: The NDC code (will be normalized)
        field_key: The field to retrieve
        drug_name: The drug name to use as fallback
        
    Returns:
        Dictionary with the field content and metadata or None if not found
    """
    queries = []
    
    # Build prioritized query list
    if ndc:
        ndc_clean = normalize_ndc(ndc)
        if ndc_clean:
            queries.append((f'openfda.product_ndc.exact:"{ndc_clean}"', f"NDC {ndc_clean}"))
    
    if drug_name:
        # Try exact generic name match
        safe_name = drug_name.replace('"', '')
        queries.append((f'openfda.generic_name:"{safe_name}"', f"Generic name {safe_name}"))
        
        # Try exact brand name match
        queries.append((f'openfda.brand_name:"{safe_name}"', f"Brand name {safe_name}"))
        
        # Try partial generic name match
        queries.append((f'openfda.generic_name:{safe_name}', f"Generic name partial {safe_name}"))
        
        # Try partial brand name match
        queries.append((f'openfda.brand_name:{safe_name}', f"Brand name partial {safe_name}"))
    
    # Add API key if available
    api_key = get_api_key()
    
    # Try each query in order
    for query, query_type in queries:
        # Preserve special characters needed for FDA query syntax
        safe_chars = '():+"'
        encoded_query = urllib.parse.quote(query, safe=safe_chars)
        
        params = {
            "search": encoded_query,
            "limit": 1
        }
        
        if api_key:
            params["api_key"] = api_key
        
        try:
            logger.info(f"Querying FDA for field '{field_key}' with {query_type}")
            response = requests.get(FDA_LABEL_API_URL, params=params)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                continue
                
            result = results[0]
            result_data = {}
            
            # First check if field exists directly in top level
            if field_key in result:
                value = result[field_key]
                logger.debug(f"Found '{field_key}' in top-level for {query_type}")
                result_data['value'] = value
                result_data['source'] = 'top-level'
                result_data['query'] = query_type
                return result_data
                
            # Then check in openfda sub-object
            openfda = result.get('openfda', {})
            if field_key in openfda:
                value = openfda[field_key]
                logger.debug(f"Found '{field_key}' in openfda sub-object for {query_type}")
                result_data['value'] = value
                result_data['source'] = 'openfda'
                result_data['query'] = query_type
                return result_data
                
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error in FDA API query for {query_type}: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error in FDA API query: {e}")
            continue
    
    # No successful queries
    return None

def lookup_ndcs_for_name(drug_name: str, limit: int = 10) -> List[str]:
    """
    Look up NDCs for a given drug name using the FDA NDC directory.
    
    Implements PillQ's successful NDC search strategy.
    
    Args:
        drug_name: The generic or brand name of the drug
        limit: Maximum number of NDCs to return
        
    Returns:
        List of NDCs (normalized to product-level)
    """
    if not drug_name:
        return []
        
    # Convert to uppercase for better matching with FDA database
    uppercase_term = drug_name.upper()
    
    # Create query with proper syntax
    raw_expr = f'(brand_name:"{uppercase_term}" OR generic_name:"{uppercase_term}")'
    
    # Preserve special characters needed for FDA query syntax
    safe_chars = '()+:"'
    encoded_expr = urllib.parse.quote(raw_expr, safe=safe_chars)
    
    params = {
        "search": encoded_expr,
        "limit": limit
    }
    
    # Add API key if available
    api_key = get_api_key()
    if api_key:
        params["api_key"] = api_key
    
    try:
        logger.info(f"Looking up NDCs for drug name: {drug_name}")
        resp = requests.get(FDA_NDC_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        ndc_list = []
        if "results" in data and data["results"]:
            for record in data["results"]:
                product_ndc = record.get("product_ndc", "")
                if product_ndc:
                    # Normalize NDC to ensure consistent format
                    ndc_list.append(normalize_ndc(product_ndc))
        
        # Deduplicate the list
        unique_ndcs = list(set(ndc_list))
        logger.info(f"Found {len(unique_ndcs)} unique NDCs for {drug_name}")
        return unique_ndcs
    except Exception as e:
        logger.error(f"Error looking up NDCs for {drug_name}: {str(e)}")
        return []

def get_drug_label_info(drug_name: Optional[str] = None, 
                       ndc: Optional[str] = None, 
                       fields: List[str] = None) -> Dict[str, Any]:
    """
    Get comprehensive label information for a drug using PillQ's proven strategy.
    
    1. Try both name-based and NDC-based searches
    2. If NDC provided, try that first
    3. If name provided, lookup NDCs and try each one
    4. Check both top-level and openfda sub-object for each field
    5. Return all found fields with their sources
    
    Args:
        drug_name: Generic or brand name of the drug
        ndc: NDC code if known
        fields: Specific fields to retrieve, or None for all important fields
        
    Returns:
        Dictionary with all found fields and metadata
    """
    result = {
        'drug_name': drug_name,
        'success': False,
        'fields_found': [],
        'ndcs_tried': [],
        'metadata': {}
    }
    
    if fields is None:
        fields = IMPORTANT_FIELDS
    
    # Gather NDCs to try
    ndcs_to_try = []
    
    if ndc:
        ndcs_to_try.append(ndc)
        
    if drug_name:
        # Lookup NDCs for drug name
        more_ndcs = lookup_ndcs_for_name(drug_name)
        ndcs_to_try.extend(more_ndcs)
        
    # Use unique NDCs only
    ndcs_to_try = list(set(ndcs_to_try))
    result['ndcs_tried'] = ndcs_to_try
    
    if not ndcs_to_try and not drug_name:
        logger.error(f"No NDCs found and no drug name provided")
        return result
        
    # Try each field with multiple approaches
    for field_key in fields:
        found = False
        
        # APPROACH 1: Try name-based search first (often more reliable than NDC-based)
        if drug_name:
            field_data = get_field_from_openfda(field_key=field_key, drug_name=drug_name)
            if field_data:
                # Add field to result
                result[field_key] = field_data['value']
                if field_key not in result['fields_found']:
                    result['fields_found'].append(field_key)
                
                # Record source information
                if 'field_sources' not in result['metadata']:
                    result['metadata']['field_sources'] = {}
                
                result['metadata']['field_sources'][field_key] = {
                    'query_type': field_data['query'],
                    'source': field_data['source']
                }
                
                found = True
                continue
        
        # APPROACH 2: Try each NDC for this field
        for ndc in ndcs_to_try:
            field_data = get_field_from_openfda(ndc=ndc, field_key=field_key)
            if field_data:
                # Add field to result
                result[field_key] = field_data['value']
                if field_key not in result['fields_found']:
                    result['fields_found'].append(field_key)
                    
                # Record source information
                if 'field_sources' not in result['metadata']:
                    result['metadata']['field_sources'] = {}
                
                result['metadata']['field_sources'][field_key] = {
                    'ndc': ndc,
                    'query_type': field_data['query'],
                    'source': field_data['source']
                }
                
                found = True
                break
                
        if not found:
            logger.debug(f"Field '{field_key}' not found with any strategy")
    
    result['success'] = len(result['fields_found']) > 0
    return result
