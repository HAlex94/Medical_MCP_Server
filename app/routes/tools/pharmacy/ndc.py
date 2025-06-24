"""
NDC (National Drug Code) Directory Module

This module provides tools for accessing product information from the FDA NDC Directory,
including cross-references to other coding systems (RxNorm, SNOMED) for EHR integration.
"""
import logging
from typing import Dict, Any, List, Optional
from app.utils.api_clients import make_request, get_api_key

logger = logging.getLogger(__name__)

# FDA NDC API endpoints
FDA_API_BASE = "https://api.fda.gov/drug"
FDA_NDC_ENDPOINT = f"{FDA_API_BASE}/ndc.json"

# RxNav API endpoints for cross-referencing
RXNAV_API_BASE = "https://rxnav.nlm.nih.gov/REST"
RXNAV_RXCUI_ENDPOINT = f"{RXNAV_API_BASE}/rxcui.json"
RXNAV_PROPERTIES_ENDPOINT = f"{RXNAV_API_BASE}/rxcui"

# Constants for API access without keys
UNAUTH_REQUEST_LIMIT = 5  # Smaller limit for unauthenticated API calls
MAX_RETRIES = 2  # Maximum retry attempts for API calls

async def enhanced_ndc_lookup(
    search_term: str,
    search_type: str = "ndc"
) -> Dict[str, Any]:
    """
    Comprehensive product lookup with packaging, formulation details,
    and cross-references to other coding systems.
    
    Args:
        search_term: The NDC, product name fragment, or manufacturer to search for
        search_type: Type of search ("ndc", "product_name", "manufacturer")
        
    Returns:
        Dictionary containing detailed product information
    """
    logger.info(f"Looking up product information for {search_term} (search type: {search_type})")
    
    # Get FDA API key if available
    fda_api_key = get_api_key("FDA_API_KEY")
    
    try:
        # Build FDA API query based on search type
        if search_type == "ndc":
            search_query = f"product_ndc:{search_term}"
        elif search_type == "product_name":
            search_query = f"brand_name:{search_term}+generic_name:{search_term}"
        elif search_type == "manufacturer":
            search_query = f"openfda.manufacturer_name:{search_term}"
        else:
            return {
                "status": "error",
                "message": f"Invalid search_type: {search_type}",
                "search_term": search_term,
                "products": []
            }
        
        # Set up API parameters with smaller limit for unauthenticated access
        params = {
            "search": search_query,
            "limit": UNAUTH_REQUEST_LIMIT
        }
        
        # Add API key to params if available
        if fda_api_key:
            params["api_key"] = fda_api_key
            # We can request more results with an API key
            params["limit"] = 10
        
        # Make request to FDA NDC API
        response = await make_request(
            url=FDA_NDC_ENDPOINT,
            params=params,
            method="GET"
        )
        
        if not response or "results" not in response:
            return {
                "status": "error",
                "message": "No results found in FDA NDC database",
                "search_term": search_term,
                "products": []
            }
        
        # Process and extract relevant product information
        products = []
        for result in response.get("results", []):
            # Extract basic product info
            product = {
                "product_ndc": result.get("product_ndc", "Unknown NDC"),
                "product_type": result.get("product_type", "Unknown type"),
                "brand_name": result.get("brand_name", ""),
                "generic_name": result.get("generic_name", ""),
                "manufacturer_name": result.get("openfda", {}).get("manufacturer_name", ["Unknown"])[0],
                "dosage_form": result.get("dosage_form", "Unknown form"),
                "route": result.get("route", ["Unknown"])[0] if result.get("route") else "Unknown",
                "active_ingredients": [],
                "packaging": [],
                "marketing_status": result.get("marketing_status", "Unknown"),
                "rx_otc": "Prescription (Rx)" if result.get("openfda", {}).get("prescription_otc_txt", [""])[0] == "Rx" else "Over-the-Counter (OTC)",
            }
            
            # Extract active ingredients
            for ingredient in result.get("active_ingredients", []):
                product["active_ingredients"].append({
                    "name": ingredient.get("name", "Unknown ingredient"),
                    "strength": ingredient.get("strength", "Unknown strength")
                })
            
            # Extract packaging information
            for package in result.get("packaging", []):
                product["packaging"].append({
                    "package_ndc": package.get("package_ndc", "Unknown package NDC"),
                    "description": package.get("description", "No description"),
                    "marketing_start_date": package.get("marketing_start_date", "Unknown"),
                    "marketing_end_date": package.get("marketing_end_date", "")
                })
            
            # Get RxNorm data if possible using the product name
            try:
                rxnorm_data = await get_rxnorm_data(product["brand_name"] if product["brand_name"] else product["generic_name"])
                if rxnorm_data:
                    product["rxnorm"] = rxnorm_data
            except Exception as e:
                logger.error(f"Failed to fetch RxNorm data: {e}")
                product["rxnorm"] = {"status": "error", "message": "Failed to fetch RxNorm data"}
            
            products.append(product)
        
        return {
            "status": "success",
            "message": f"Found {len(products)} products matching '{search_term}'",
            "search_term": search_term,
            "search_type": search_type,
            "products": products
        }
        
    except Exception as e:
        logger.error(f"Error searching FDA NDC database: {e}")
        return {
            "status": "error",
            "message": f"Error searching FDA NDC database: {str(e)}",
            "search_term": search_term,
            "products": []
        }

async def get_rxnorm_data(drug_name: str) -> Dict[str, Any]:
    """
    Get RxNorm data for a drug to provide coding system cross-references.
    
    Args:
        drug_name: Name of the drug to look up
        
    Returns:
        Dictionary containing RxNorm identifiers and related information
    """
    try:
        # Get RxCUI (RxNorm Concept Unique Identifier)
        params = {
            "name": drug_name,
            "search": 2  # Search by approximate match
        }
        
        rxcui_response = await make_request(
            url=RXNAV_RXCUI_ENDPOINT,
            params=params,
            method="GET"
        )
        
        if not rxcui_response or "idGroup" not in rxcui_response:
            return {"status": "not_found", "message": "No RxNorm data found"}
        
        rxcui_list = rxcui_response["idGroup"].get("rxnormId", [])
        if not rxcui_list:
            return {"status": "not_found", "message": "No RxCUI found for this medication"}
        
        # Use first RxCUI to get additional properties
        rxcui = rxcui_list[0]
        
        # Get drug properties and relationships - RxNav API allows unauthenticated access
        try:
            properties_url = f"{RXNAV_PROPERTIES_ENDPOINT}/{rxcui}/allProperties.json"
            properties_response = await make_request(
                url=properties_url,
                method="GET"
            )
        except Exception as e:
            logger.warning(f"Error retrieving RxNav properties, trying alternative endpoint: {e}")
            
            # Try the alternative endpoint for properties
            try:
                properties_url = f"{RXNAV_BASE_URL}/REST/rxcui/{rxcui}/properties.json"
                properties_response = await make_request(
                    url=properties_url,
                    method="GET"
                )
            except Exception as e2:
                logger.error(f"All property endpoint attempts failed: {e2}")
                properties_response = None
        
        if not properties_response or "propConceptGroup" not in properties_response:
            return {
                "status": "partial",
                "rxcui": rxcui,
                "message": "Found RxCUI but no additional properties"
            }
        
        # Extract property information
        properties = properties_response.get("propConceptGroup", {}).get("propConcept", [])
        
        # Organize properties by category
        organized_props = {
            "identifiers": {"rxcui": rxcui},
            "names": {},
            "attributes": {}
        }
        
        for prop in properties:
            prop_name = prop.get("propName")
            prop_value = prop.get("propValue")
            
            if prop_name in ["RxNorm Name", "Display Name", "Synonym"]:
                organized_props["names"][prop_name] = prop_value
            elif prop_name in ["TTY", "RXAUI", "UMLS_CUI"]:
                organized_props["identifiers"][prop_name] = prop_value
            else:
                organized_props["attributes"][prop_name] = prop_value
        
        return {
            "status": "success",
            "message": "RxNorm data retrieved successfully",
            "rxnorm_data": organized_props
        }
    
    except Exception as e:
        logger.error(f"Error retrieving RxNorm data: {e}")
        return {"status": "error", "message": f"Error retrieving RxNorm data: {str(e)}"}
