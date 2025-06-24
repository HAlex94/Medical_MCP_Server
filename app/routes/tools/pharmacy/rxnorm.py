"""
RxNorm API Integration Module

This module provides tools for mapping medication names across different
coding systems (NDC, RxNorm, GPI), which is essential for EHR system 
integration and terminology standardization.
"""
import logging
from typing import Dict, Any, List, Optional
from app.utils.api_clients import make_request, get_api_key

logger = logging.getLogger(__name__)

# RxNav API endpoints
RXNAV_API_BASE = "https://rxnav.nlm.nih.gov/REST"
RXNORM_API_ENDPOINTS = {
    "rxcui": f"{RXNAV_API_BASE}/rxcui",                     # Get RxCUI by name
    "properties": f"{RXNAV_API_BASE}/rxcui/{{rxcui}}/allProperties",  # Get properties by RxCUI
    "propertiesAlt": f"{RXNAV_API_BASE}/rxcui/{{rxcui}}/properties",  # Alternative properties endpoint
    "ndc": f"{RXNAV_API_BASE}/rxcui/{{rxcui}}/ndcs",        # Get NDCs by RxCUI
    "atc": f"{RXNAV_API_BASE}/rxclass/class/byRxcui",       # Get ATC classes
    "interaction": f"{RXNAV_API_BASE}/interaction/interaction", # Drug interactions
    "spelling": f"{RXNAV_API_BASE}/spellingsuggestions",    # Spelling suggestions
    "approximateTerm": f"{RXNAV_API_BASE}/approximateTerm", # Approximate term match
}

# Constants for unauthenticated API access
MAX_RETRIES = 2  # Maximum retry attempts
UNAUTH_REQUEST_LIMIT = 5  # Lower result limit for unauthenticated requests

# Map source vocabulary codes to RxNav parameters
SOURCE_VOCAB_MAP = {
    "rxnorm": None,  # Already RxNorm
    "ndc": "NDC",
    "gpi": "GPI",
    "atc": "ATC",
    "snomed": "SNOMEDCT",
    "mesh": "MSH",
    "icd10": "ICD10",
}

async def rxnorm_mapping(
    medication_name: str,
    source_vocabulary: Optional[str] = None
) -> Dict[str, Any]:
    """
    Map medication names across coding systems (NDC, RxNorm, GPI).
    
    Args:
        medication_name: Name or code of the medication
        source_vocabulary: The vocabulary system the input is in ("rxnorm", "ndc", "gpi", etc.)
                          If None, assumed to be a medication name.
    
    Returns:
        Dictionary with mappings across terminology systems
    """
    logger.info(f"Mapping '{medication_name}' across terminologies (source: {source_vocabulary or 'name'})")
    
    try:
        rxcui = None
        
        # Step 1: Get RxCUI based on source vocabulary
        if source_vocabulary and source_vocabulary.lower() in SOURCE_VOCAB_MAP:
            if source_vocabulary.lower() == "ndc":
                # Special handling for NDC codes (different endpoint)
                rxcui = await get_rxcui_from_ndc(medication_name)
            elif SOURCE_VOCAB_MAP[source_vocabulary.lower()]:
                # Get RxCUI from source term using specified vocabulary
                rxcui = await get_rxcui_from_source(
                    medication_name, 
                    SOURCE_VOCAB_MAP[source_vocabulary.lower()]
                )
        else:
            # Assume it's a medication name
            rxcui = await get_rxcui_from_name(medication_name)
            
        if not rxcui:
            return {
                "status": "error",
                "message": f"Could not find RxCUI for '{medication_name}'",
                "input": medication_name,
                "source_vocabulary": source_vocabulary
            }
        
        # Step 2: Get terminology mappings using the RxCUI
        mappings = await get_terminology_mappings(rxcui)
        
        # Step 3: Get additional medication information
        med_info = await get_medication_info(rxcui)
        
        return {
            "status": "success",
            "input": medication_name,
            "source_vocabulary": source_vocabulary,
            "rxcui": rxcui,
            "mappings": mappings,
            "medication_info": med_info
        }
    
    except Exception as e:
        logger.error(f"Error in RxNorm mapping: {e}")
        return {
            "status": "error",
            "message": f"Error in RxNorm mapping: {str(e)}",
            "input": medication_name,
            "source_vocabulary": source_vocabulary
        }

async def get_rxcui_from_name(name: str) -> Optional[str]:
    """Get RxCUI from medication name"""
    try:
        params = {
            "name": name,
            "search": 2  # Approximate match
        }
        
        response = await make_request(
            url=f"{RXNAV_API_BASE}/rxcui.json",
            params=params,
            method="GET"
        )
        
        if response and "idGroup" in response:
            rxcui_list = response["idGroup"].get("rxnormId", [])
            if rxcui_list:
                return rxcui_list[0]
        
        # Try approximate match if exact match fails
        approx_params = {
            "term": name,
            "maxEntries": 1
        }
        
        approx_response = await make_request(
            url=f"{RXNAV_API_BASE}/approximateTerm.json",
            params=approx_params,
            method="GET"
        )
        
        if approx_response and "approximateGroup" in approx_response:
            candidates = approx_response["approximateGroup"].get("candidate", [])
            if candidates:
                # Now get the rxcui for this candidate term
                term = candidates[0].get("name")
                if term:
                    return await get_rxcui_from_name(term)
        
        return None
    except Exception as e:
        logger.error(f"Error getting RxCUI from name: {e}")
        return None

async def get_rxcui_from_ndc(ndc: str) -> Optional[str]:
    """Get RxCUI from NDC code"""
    try:
        params = {
            "idtype": "NDC",
            "id": ndc
        }
        
        response = await make_request(
            url=f"{RXNAV_API_BASE}/rxcui.json",
            params=params,
            method="GET"
        )
        
        if response and "idGroup" in response:
            rxcui_list = response["idGroup"].get("rxnormId", [])
            if rxcui_list:
                return rxcui_list[0]
        
        return None
    except Exception as e:
        logger.error(f"Error getting RxCUI from NDC: {e}")
        return None

async def get_rxcui_from_source(code: str, vocabulary: str) -> Optional[str]:
    """Get RxCUI from a source vocabulary code"""
    try:
        params = {
            "idtype": vocabulary,
            "id": code
        }
        
        response = await make_request(
            url=f"{RXNAV_API_BASE}/rxcui.json",
            params=params,
            method="GET"
        )
        
        if response and "idGroup" in response:
            rxcui_list = response["idGroup"].get("rxnormId", [])
            if rxcui_list:
                return rxcui_list[0]
        
        return None
    except Exception as e:
        logger.error(f"Error getting RxCUI from source: {e}")
        return None

async def get_terminology_mappings(rxcui: str) -> Dict[str, Any]:
    """Get mappings to other terminology systems using RxCUI"""
    mappings = {
        "rxnorm": rxcui,
        "ndc": [],
        "atc": [],
        "mesh": [],
        "snomed": [],
        "spl": []
    }
    
    try:
        # Get NDC codes
        ndc_response = await make_request(
            url=f"{RXNAV_API_BASE}/rxcui/{rxcui}/ndcs.json",
            method="GET"
        )
        
        if ndc_response and "ndcGroup" in ndc_response:
            ndc_list = ndc_response["ndcGroup"].get("ndcList", {}).get("ndc", [])
            mappings["ndc"] = ndc_list
        
        # Get property mappings
        prop_response = await make_request(
            url=f"{RXNAV_API_BASE}/rxcui/{rxcui}/property.json",
            params={"prop": "ALL"},
            method="GET"
        )
        
        if prop_response and "propConceptGroup" in prop_response:
            properties = prop_response["propConceptGroup"].get("propConcept", [])
            for prop in properties:
                prop_name = prop.get("propName", "").lower()
                prop_value = prop.get("propValue")
                
                # Map properties to terminology systems
                if prop_name == "atc" and prop_value:
                    mappings["atc"].append(prop_value)
                elif prop_name == "umlscui" and prop_value:
                    # UMLS CUI can be used to get other mappings
                    mappings["umls"] = prop_value
        
        # Get ATC classes
        atc_response = await make_request(
            url=f"{RXNAV_API_BASE}/rxclass/class/byRxcui.json",
            params={"rxcui": rxcui, "relaSource": "ATC"},
            method="GET"
        )
        
        if atc_response and "rxclassDrugInfoList" in atc_response:
            drug_info_list = atc_response["rxclassDrugInfoList"].get("rxclassDrugInfo", [])
            for drug_info in drug_info_list:
                rx_class_info = drug_info.get("rxclassMinConceptItem", {})
                class_id = rx_class_info.get("classId")
                class_name = rx_class_info.get("className")
                if class_id and class_id not in mappings["atc"]:
                    mappings["atc"].append({"code": class_id, "name": class_name})
        
        return mappings
    
    except Exception as e:
        logger.error(f"Error getting terminology mappings: {e}")
        return mappings

async def get_medication_info(rxcui: str) -> Dict[str, Any]:
    """Get detailed medication information using RxCUI"""
    try:
        info = {
            "name": {},
            "attributes": {},
            "dose_forms": []
        }
        
        # Get basic medication information
        response = await make_request(
            url=f"{RXNAV_API_BASE}/rxcui/{rxcui}/allrelated.json",
            method="GET"
        )
        
        if response and "allRelatedGroup" in response:
            concepts = response["allRelatedGroup"].get("conceptGroup", [])
            
            for concept_group in concepts:
                # Get TTY (Term Type) information
                if concept_group.get("tty") == "SCD":  # Semantic Clinical Drug
                    for concept in concept_group.get("conceptProperties", []):
                        if "name" in concept:
                            info["name"]["clinical_drug"] = concept["name"]
                elif concept_group.get("tty") == "SBD":  # Semantic Branded Drug
                    for concept in concept_group.get("conceptProperties", []):
                        if "name" in concept:
                            info["name"]["branded_drug"] = concept["name"]
                elif concept_group.get("tty") == "GPCK":  # Generic Pack
                    for concept in concept_group.get("conceptProperties", []):
                        if "name" in concept:
                            info["name"]["generic_pack"] = concept["name"]
                elif concept_group.get("tty") == "DF":  # Dose Form
                    for concept in concept_group.get("conceptProperties", []):
                        if "name" in concept:
                            info["dose_forms"].append(concept["name"])
        
        # Get additional properties
        prop_response = await make_request(
            url=f"{RXNAV_API_BASE}/rxcui/{rxcui}/allProperties.json",
            params={"prop": "names"},
            method="GET"
        )
        
        if prop_response and "propConceptGroup" in prop_response:
            properties = prop_response["propConceptGroup"].get("propConcept", [])
            
            for prop in properties:
                prop_name = prop.get("propName")
                prop_value = prop.get("propValue")
                
                if prop_name == "RxNorm Name":
                    info["name"]["rxnorm"] = prop_value
                elif prop_name == "Synonym":
                    if "synonyms" not in info["name"]:
                        info["name"]["synonyms"] = []
                    info["name"]["synonyms"].append(prop_value)
                elif prop_name == "BN":  # Brand Name
                    info["name"]["brand"] = prop_value
        
        return info
    
    except Exception as e:
        logger.error(f"Error getting medication info: {e}")
        return {"error": str(e)}
