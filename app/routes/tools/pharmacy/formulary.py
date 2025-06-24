"""
Formulary Management Assistant Module

This module provides tools to find therapeutic alternatives within the same class
to assist with formulary management decisions.
"""
import logging
from typing import Dict, Any, List, Optional
from app.utils.api_clients import make_request, get_api_key

logger = logging.getLogger(__name__)

# API endpoints
FDA_API_BASE = "https://api.fda.gov/drug"
RXNAV_API_BASE = "https://rxnav.nlm.nih.gov/REST"
RXNAV_CLASSES_ENDPOINT = f"{RXNAV_API_BASE}/rxclass/class"
RXNAV_CLASSMATES_ENDPOINT = f"{RXNAV_API_BASE}/rxclass/classMembers"

async def analyze_formulary_alternatives(
    medication: str,
    formulary_tier: Optional[str] = None,
    therapeutic_class: Optional[str] = None
) -> Dict[str, Any]:
    """
    Find therapeutic alternatives within the same class to assist
    with formulary management decisions.
    
    Args:
        medication: Name of the medication to find alternatives for
        formulary_tier: Optional tier designation for cost categorization
        therapeutic_class: Optional specification of therapeutic class
        
    Returns:
        Dictionary containing therapeutic alternatives
    """
    logger.info(f"Finding formulary alternatives for {medication}")
    
    try:
        results = {
            "status": "processing",
            "input_medication": medication,
            "therapeutic_class": therapeutic_class,
            "alternatives": []
        }
        
        # Step 1: Find RxNorm concept for the medication
        rxcui = await get_rxcui(medication)
        
        if not rxcui:
            return {
                "status": "error",
                "message": f"Could not find RxNorm concept for {medication}",
                "input_medication": medication,
                "alternatives": []
            }
        
        results["rxcui"] = rxcui
        
        # Step 2: Find drug classes for this medication
        classes = await get_drug_classes(rxcui)
        
        if not classes:
            return {
                "status": "error",
                "message": f"Could not find therapeutic classes for {medication}",
                "input_medication": medication,
                "rxcui": rxcui,
                "alternatives": []
            }
            
        # Filter by therapeutic class if provided
        filtered_classes = classes
        if therapeutic_class:
            filtered_classes = [cls for cls in classes if therapeutic_class.lower() in cls["className"].lower()]
            if not filtered_classes and classes:
                # If filtered list is empty but we have classes, use the first one
                filtered_classes = [classes[0]]
                
        results["identified_classes"] = filtered_classes
        
        # Step 3: For each class, find alternative medications
        all_alternatives = []
        
        for drug_class in filtered_classes[:3]:  # Limit to first 3 classes for performance
            class_id = drug_class.get("classId")
            class_name = drug_class.get("className")
            
            alternatives = await get_class_members(class_id)
            
            for alt in alternatives:
                # Avoid duplicates and the original medication
                if alt.get("rxcui") != rxcui and not any(a.get("rxcui") == alt.get("rxcui") for a in all_alternatives):
                    alt["class_id"] = class_id
                    alt["class_name"] = class_name
                    
                    # Add FDA information when available
                    try:
                        fda_info = await get_fda_drug_info(alt.get("name", ""))
                        if fda_info:
                            alt["fda_info"] = fda_info
                    except Exception as e:
                        logger.warning(f"Could not get FDA info for {alt.get('name')}: {e}")
                        
                    all_alternatives.append(alt)
        
        # Step 4: Sort alternatives by name
        all_alternatives.sort(key=lambda x: x.get("name", "").lower())
        
        # Add tier information if provided
        if formulary_tier:
            results["formulary_tier"] = formulary_tier
        
        results["alternatives"] = all_alternatives
        results["status"] = "success"
        results["message"] = f"Found {len(all_alternatives)} therapeutic alternatives for {medication}"
        
        return results
    
    except Exception as e:
        logger.error(f"Error analyzing formulary alternatives: {e}")
        return {
            "status": "error",
            "message": f"Error analyzing formulary alternatives: {str(e)}",
            "input_medication": medication,
            "alternatives": []
        }

async def get_rxcui(medication_name: str) -> Optional[str]:
    """Get RxCUI for a medication name"""
    try:
        params = {
            "name": medication_name,
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
        
        return None
    except Exception as e:
        logger.error(f"Error getting RxCUI: {e}")
        return None

async def get_drug_classes(rxcui: str) -> List[Dict[str, Any]]:
    """Get therapeutic classes for a medication by RxCUI"""
    classes = []
    
    try:
        # Try multiple class types to ensure good coverage
        for class_type in ["ATC", "EPC", "MOA", "VA"]:
            params = {
                "rxcui": rxcui,
                "relaSource": class_type
            }
            
            response = await make_request(
                url=f"{RXNAV_CLASSES_ENDPOINT}/byRxcui.json",
                params=params,
                method="GET"
            )
            
            if response and "rxclassDrugInfoList" in response:
                drug_info_list = response["rxclassDrugInfoList"].get("rxclassDrugInfo", [])
                
                for drug_info in drug_info_list:
                    rx_class = drug_info.get("rxclassMinConceptItem", {})
                    
                    class_info = {
                        "classId": rx_class.get("classId"),
                        "className": rx_class.get("className"),
                        "classType": rx_class.get("classType")
                    }
                    
                    # Avoid duplicates
                    if not any(c["classId"] == class_info["classId"] for c in classes):
                        classes.append(class_info)
        
        return classes
    except Exception as e:
        logger.error(f"Error getting drug classes: {e}")
        return []

async def get_class_members(class_id: str) -> List[Dict[str, Any]]:
    """Get members (drugs) of a therapeutic class"""
    members = []
    
    try:
        params = {
            "classId": class_id,
            "sourceType": 1  # "DRUG_SOURCE" filter to get human drugs
        }
        
        response = await make_request(
            url=f"{RXNAV_CLASSMATES_ENDPOINT}.json",
            params=params,
            method="GET"
        )
        
        if response and "drugMemberGroup" in response:
            drug_members = response["drugMemberGroup"].get("drugMember", [])
            
            for drug in drug_members:
                member_info = {
                    "rxcui": drug.get("rxcui"),
                    "name": drug.get("name"),
                    "source": drug.get("source"),
                    "rela": drug.get("rela")
                }
                members.append(member_info)
        
        return members
    except Exception as e:
        logger.error(f"Error getting class members: {e}")
        return []

async def get_fda_drug_info(drug_name: str) -> Optional[Dict[str, Any]]:
    """Get FDA drug information for a medication"""
    try:
        # Get FDA API key if available
        fda_api_key = get_api_key("FDA_API_KEY")
        
        # Build search query
        search_query = f"generic_name:{drug_name}+brand_name:{drug_name}"
        
        # Build params
        params = {
            "search": search_query,
            "limit": 1
        }
        
        # Add API key if available
        if fda_api_key:
            params["api_key"] = fda_api_key
        
        response = await make_request(
            url=f"{FDA_API_BASE}/ndc.json",
            params=params,
            method="GET"
        )
        
        if response and "results" in response and response["results"]:
            result = response["results"][0]
            
            drug_info = {
                "product_type": result.get("product_type"),
                "generic_name": result.get("generic_name"),
                "brand_name": result.get("brand_name", ""),
                "dosage_form": result.get("dosage_form", ""),
                "route": result.get("route", [""])[0] if result.get("route") else "",
                "marketing_status": result.get("marketing_status", ""),
                "active_ingredients": []
            }
            
            # Extract active ingredients
            for ingredient in result.get("active_ingredients", []):
                drug_info["active_ingredients"].append({
                    "name": ingredient.get("name", ""),
                    "strength": ingredient.get("strength", "")
                })
                
            return drug_info
        
        return None
    except Exception as e:
        logger.error(f"Error getting FDA drug info: {e}")
        return None
