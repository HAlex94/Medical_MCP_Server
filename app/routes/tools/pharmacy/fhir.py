"""
FHIR Resource Generator Module

This module provides tools for converting medication data into FHIR-compliant 
resources for interoperability purposes in EHR systems.
"""
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.utils.api_clients import make_request, get_api_key

logger = logging.getLogger(__name__)

async def generate_fhir_medication_resource(
    medication_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Convert medication data into FHIR-compliant resources
    for interoperability purposes.
    
    Args:
        medication_data: Dictionary containing medication information
            Required keys:
            - code: String or Dictionary (system, value) for medication code
            - display_name: Name of medication
            
            Optional keys:
            - form: Dosage form
            - ingredients: List of ingredients with strength
            - manufacturer: Manufacturer information
            - batch: Batch/lot information
            - amount: Amount information
            - status: Medication status
            - identifier: Additional identifiers
    
    Returns:
        Dictionary containing FHIR Medication resource
    """
    logger.info("Generating FHIR Medication resource")
    
    try:
        # Get medication name (support both 'name' and 'display_name' fields)
        medication_name = medication_data.get("display_name") or medication_data.get("name")
        
        if not medication_name:
            return {
                "status": "error",
                "message": "Either 'name' or 'display_name' is required in medication_data",
                "fhir_resource": None
            }
        
        # Normalize the data structure for further processing
        if "name" in medication_data and "display_name" not in medication_data:
            medication_data["display_name"] = medication_name
        
        if not medication_data.get("code"):
            return {
                "status": "error",
                "message": "code is required in medication_data",
                "fhir_resource": None
            }
        
        # Initialize FHIR Medication resource
        fhir_resource = {
            "resourceType": "Medication",
            "id": f"med-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "meta": {
                "profile": [
                    "http://hl7.org/fhir/StructureDefinition/Medication"
                ]
            },
            "status": medication_data.get("status", "active")
        }
        
        # Add codes (required)
        if isinstance(medication_data["code"], dict):
            code_obj = {
                "coding": [
                    {
                        "system": medication_data["code"].get("system", "http://www.nlm.nih.gov/research/umls/rxnorm"),
                        "code": medication_data["code"].get("value", ""),
                        "display": medication_data.get("display_name", "")
                    }
                ],
                "text": medication_data.get("display_name", "")
            }
        else:
            # Assume it's a string and use it as RxNorm code
            code_obj = {
                "coding": [
                    {
                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                        "code": str(medication_data["code"]),
                        "display": medication_data.get("display_name", "")
                    }
                ],
                "text": medication_data.get("display_name", "")
            }
        
        fhir_resource["code"] = code_obj
        
        # Add form if provided
        if medication_data.get("form"):
            fhir_resource["form"] = {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-orderableDrugForm",
                        "code": medication_data["form"].get("code", ""),
                        "display": medication_data["form"].get("display", "")
                    }
                ],
                "text": medication_data["form"].get("display", "")
            }
        
        # Add ingredients if provided
        if medication_data.get("ingredients") and isinstance(medication_data["ingredients"], list):
            fhir_resource["ingredient"] = []
            
            for ingredient in medication_data["ingredients"]:
                ing_obj = {
                    "itemCodeableConcept": {
                        "coding": [
                            {
                                "system": ingredient.get("system", "http://www.nlm.nih.gov/research/umls/rxnorm"),
                                "code": ingredient.get("code", ""),
                                "display": ingredient.get("name", "")
                            }
                        ],
                        "text": ingredient.get("name", "")
                    }
                }
                
                # Add strength if available
                if ingredient.get("strength"):
                    ing_obj["strength"] = {
                        "numerator": {
                            "value": ingredient["strength"].get("value", 0),
                            "unit": ingredient["strength"].get("unit", ""),
                            "system": "http://unitsofmeasure.org",
                            "code": ingredient["strength"].get("code", "")
                        },
                        "denominator": {
                            "value": 1,
                            "unit": "unit",
                            "system": "http://unitsofmeasure.org",
                            "code": "unit"
                        }
                    }
                
                fhir_resource["ingredient"].append(ing_obj)
        
        # Add manufacturer if provided
        if medication_data.get("manufacturer"):
            fhir_resource["manufacturer"] = {
                "reference": f"Organization/{medication_data['manufacturer'].get('id', 'unknown')}",
                "display": medication_data["manufacturer"].get("name", "Unknown Manufacturer")
            }
        
        # Add batch information if provided
        if medication_data.get("batch"):
            fhir_resource["batch"] = {
                "lotNumber": medication_data["batch"].get("lotNumber", ""),
                "expirationDate": medication_data["batch"].get("expirationDate", "")
            }
        
        # Add amount information if provided
        if medication_data.get("amount"):
            fhir_resource["amount"] = {
                "numerator": {
                    "value": medication_data["amount"].get("value", 0),
                    "unit": medication_data["amount"].get("unit", ""),
                    "system": "http://unitsofmeasure.org",
                    "code": medication_data["amount"].get("code", "")
                },
                "denominator": {
                    "value": 1,
                    "unit": "unit",
                    "system": "http://unitsofmeasure.org",
                    "code": "unit"
                }
            }
        
        # Add identifiers if provided
        if medication_data.get("identifier") and isinstance(medication_data["identifier"], list):
            fhir_resource["identifier"] = []
            
            for identifier in medication_data["identifier"]:
                fhir_resource["identifier"].append({
                    "system": identifier.get("system", ""),
                    "value": identifier.get("value", ""),
                    "use": identifier.get("use", "official")
                })
        
        return {
            "status": "success",
            "message": "Successfully generated FHIR Medication resource",
            "fhir_resource": fhir_resource
        }
        
    except Exception as e:
        logger.error(f"Error generating FHIR resource: {e}")
        return {
            "status": "error",
            "message": f"Error generating FHIR resource: {str(e)}",
            "fhir_resource": None
        }

async def convert_ndc_to_fhir(ndc_code: str) -> Dict[str, Any]:
    """
    Convert an NDC code to a FHIR Medication resource by first
    looking up the NDC information.
    
    Args:
        ndc_code: National Drug Code to convert
        
    Returns:
        Dictionary containing FHIR Medication resource
    """
    logger.info(f"Converting NDC {ndc_code} to FHIR Medication resource")
    
    try:
        # Get FDA API key if available
        fda_api_key = get_api_key("FDA_API_KEY")
        
        # Build search query
        search_query = f"product_ndc:{ndc_code}"
        
        # Build params
        params = {
            "search": search_query,
            "limit": 1
        }
        
        # Add API key if available
        if fda_api_key:
            params["api_key"] = fda_api_key
        
        # Query FDA NDC API
        response = await make_request(
            url=f"https://api.fda.gov/drug/ndc.json",
            params=params,
            method="GET"
        )
        
        if not response or "results" not in response or not response["results"]:
            return {
                "status": "error",
                "message": f"No results found for NDC {ndc_code}",
                "fhir_resource": None
            }
        
        # Get the first result
        result = response["results"][0]
        
        # Extract medication information
        medication_data = {
            "display_name": result.get("brand_name") or result.get("generic_name", "Unknown Medication"),
            "code": {
                "system": "http://hl7.org/fhir/sid/ndc",
                "value": ndc_code
            },
            "status": "active"
        }
        
        # Add form if available
        if result.get("dosage_form"):
            medication_data["form"] = {
                "display": result.get("dosage_form"),
                "code": result.get("dosage_form").lower().replace(" ", "-")
            }
        
        # Add ingredients if available
        if result.get("active_ingredients"):
            medication_data["ingredients"] = []
            
            for ingredient in result.get("active_ingredients", []):
                ing = {
                    "name": ingredient.get("name", "Unknown Ingredient"),
                    "code": "",  # We don't have RxNorm codes from FDA API
                }
                
                # Parse strength if available
                if ingredient.get("strength"):
                    strength_str = ingredient.get("strength", "")
                    # Simple parsing - would need more robust implementation for production
                    numeric_part = ''.join(c for c in strength_str if c.isdigit() or c == '.')
                    unit_part = ''.join(c for c in strength_str if not c.isdigit() and c != '.')
                    
                    try:
                        value = float(numeric_part) if numeric_part else 0
                        ing["strength"] = {
                            "value": value,
                            "unit": unit_part.strip(),
                            "code": unit_part.strip()
                        }
                    except ValueError:
                        pass
                
                medication_data["ingredients"].append(ing)
        
        # Add manufacturer if available
        if result.get("openfda", {}).get("manufacturer_name"):
            manufacturer_name = result["openfda"]["manufacturer_name"][0]
            medication_data["manufacturer"] = {
                "name": manufacturer_name,
                "id": "org-" + manufacturer_name.lower().replace(" ", "-")
            }
        
        # Add packaging identifiers
        if result.get("packaging"):
            medication_data["identifier"] = []
            
            for package in result.get("packaging", []):
                if package.get("package_ndc"):
                    medication_data["identifier"].append({
                        "system": "http://hl7.org/fhir/sid/ndc",
                        "value": package.get("package_ndc"),
                        "use": "official"
                    })
        
        # Generate FHIR resource
        return await generate_fhir_medication_resource(medication_data)
        
    except Exception as e:
        logger.error(f"Error converting NDC to FHIR: {e}")
        return {
            "status": "error",
            "message": f"Error converting NDC to FHIR: {str(e)}",
            "fhir_resource": None
        }
