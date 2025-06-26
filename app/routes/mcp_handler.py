from fastapi import APIRouter, Request, Response, status
import json
import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

# Import tool modules
from app.routes.tools import pubmed, fda, trials
from app.routes.tools.pharmacy import ndc, rxnorm, evidence, formulary, fhir
from app.prompt_templates import pharmacy as pharmacy_templates
from app.resources.fda_drug_resources import FDA_DRUG_RESOURCES

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["MCP Endpoints"])

# MCP Protocol Models
class FunctionDef(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]

class Resource(BaseModel):
    uri: str
    name: str
    description: str = ""
    type: str = "function"
    function: Optional[FunctionDef] = None
    authentication: Optional[Dict[str, Any]] = None

class MCPError(BaseModel):
    message: str
    code: str = "internal_error"

# MCP Protocol Endpoints
@router.post("/resources/list")
async def list_resources(request: Request):
    """
    List available medical data resources to be used as tools by ChatGPT.
    
    This endpoint follows the MCP protocol for resource discovery.
    """
    try:
        body = await request.json()
        cursor = body.get("cursor", "")
        
        # Collect all available resources from tool modules
        resources = [
            # Optimized FDA Drug Resources with pagination
            Resource(
                uri="fda/drug/search",
                name="FDA Drug Products Search",
                description="Search for medication products with compact results and pagination to avoid size limitations",
                function=FunctionDef(
                    name="search_drug_products",
                    description="Search for drug products by name, manufacturer, active ingredient, or NDC",
                    parameters={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Brand or generic name of the drug (e.g., apixaban, Eliquis)"
                            },
                            "manufacturer": {
                                "type": "string",
                                "description": "Name of the manufacturer (e.g., Bristol Myers Squibb)"
                            },
                            "active_ingredient": {
                                "type": "string",
                                "description": "Active ingredient in the drug (e.g., apixaban)"
                            },
                            "ndc": {
                                "type": "string",
                                "description": "National Drug Code"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return (use lower values to avoid ResponseTooLargeError)",
                                "default": 10
                            },
                            "skip": {
                                "type": "integer",
                                "description": "Number of results to skip for pagination",
                                "default": 0
                            }
                        }
                    }
                )
            ),
            
            # Original FDA Drug Resources
            # FDA Drug Information
            Resource(
                uri="fda/drug_lookup",
                name="FDA Drug Lookup",
                description="Search for medication information from the FDA database",
                function=FunctionDef(
                    name="search_medication",
                    description="Search for medication information by name or active ingredient",
                    parameters={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Medication name or active ingredient"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 5
                            }
                        },
                        "required": ["query"]
                    }
                )
            ),
            
            # FDA Drug Label Data
            Resource(
                uri="fda/label/data",
                name="FDA Drug Label Data",
                description="Retrieve specific sections from FDA drug labels including indications, active ingredients, warnings, etc.",
                function=FunctionDef(
                    name="get_drug_label_data",
                    description="Retrieve specific sections from FDA drug labels",
                    parameters={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Brand or generic drug name"
                            },
                            "fields": {
                                "type": "string",
                                "description": "Comma-separated list of label fields to retrieve (e.g., 'indications_and_usage,warnings,active_ingredient'). If not specified, returns all available fields.",
                                "default": ""
                            }
                        },
                        "required": ["name"]
                    }
                )
            ),
            
            # Enhanced NDC Lookup
            Resource(
                uri="pharmacy/ndc_lookup",
                name="Enhanced NDC Lookup",
                description="Comprehensive product information with cross-references to other coding systems",
                function=FunctionDef(
                    name="enhanced_ndc_lookup",
                    description="Lookup detailed product information by NDC, product name, or manufacturer",
                    parameters={
                        "type": "object",
                        "properties": {
                            "search_term": {
                                "type": "string",
                                "description": "NDC, product name, or manufacturer to search for"
                            },
                            "search_type": {
                                "type": "string",
                                "description": "Type of search (ndc, product_name, manufacturer)",
                                "default": "ndc",
                                "enum": ["ndc", "product_name", "manufacturer"]
                            }
                        },
                        "required": ["search_term"]
                    }
                )
            ),
            
            # RxNorm Mapping
            Resource(
                uri="pharmacy/rxnorm_mapping",
                name="RxNorm Terminology Mapping",
                description="Map medication names across coding systems (NDC, RxNorm, GPI)",
                function=FunctionDef(
                    name="rxnorm_mapping",
                    description="Map medication names or codes across terminology systems",
                    parameters={
                        "type": "object",
                        "properties": {
                            "medication_name": {
                                "type": "string",
                                "description": "Name or code of the medication"
                            },
                            "source_vocabulary": {
                                "type": "string",
                                "description": "Source vocabulary type (rxnorm, ndc, gpi, etc.)",
                                "enum": ["rxnorm", "ndc", "gpi", "atc", "snomed", "mesh", "icd10", null]
                            }
                        },
                        "required": ["medication_name"]
                    }
                )
            ),
            
            # Evidence-Based Order Set Builder
            Resource(
                uri="pharmacy/order_set_evidence",
                name="Evidence-Based Order Set Builder",
                description="Retrieve evidence-based recommendations for order sets in EHR systems",
                function=FunctionDef(
                    name="get_evidence_for_order_set",
                    description="Get evidence-based recommendations for clinical condition order sets",
                    parameters={
                        "type": "object",
                        "properties": {
                            "condition": {
                                "type": "string",
                                "description": "The clinical condition or disease"
                            },
                            "intervention_type": {
                                "type": "string",
                                "description": "Type of intervention (medication, lab, imaging)",
                                "default": "medication",
                                "enum": ["medication", "lab", "imaging"]
                            }
                        },
                        "required": ["condition"]
                    }
                )
            ),
            
            # Formulary Management Assistant
            Resource(
                uri="pharmacy/formulary_alternatives",
                name="Formulary Management Assistant",
                description="Find therapeutic alternatives within the same class for formulary management",
                function=FunctionDef(
                    name="analyze_formulary_alternatives",
                    description="Find therapeutic alternatives for a medication",
                    parameters={
                        "type": "object",
                        "properties": {
                            "medication": {
                                "type": "string",
                                "description": "Name of the medication to find alternatives for"
                            },
                            "formulary_tier": {
                                "type": "string",
                                "description": "Optional tier designation for cost categorization"
                            },
                            "therapeutic_class": {
                                "type": "string",
                                "description": "Optional specification of therapeutic class"
                            }
                        },
                        "required": ["medication"]
                    }
                )
            ),
            
            # FHIR Resource Generator
            Resource(
                uri="pharmacy/fhir_medication",
                name="FHIR Medication Resource Generator",
                description="Convert medication data to FHIR-compliant resources",
                function=FunctionDef(
                    name="generate_fhir_medication_resource",
                    description="Convert medication data into FHIR Medication resource",
                    parameters={
                        "type": "object",
                        "properties": {
                            "medication_data": {
                                "type": "object",
                                "description": "Medication data to convert to FHIR"
                            }
                        },
                        "required": ["medication_data"]
                    }
                )
            ),
            
            # NDC to FHIR Converter
            Resource(
                uri="pharmacy/ndc_to_fhir",
                name="NDC to FHIR Converter",
                description="Convert an NDC code to a FHIR Medication resource",
                function=FunctionDef(
                    name="convert_ndc_to_fhir",
                    description="Convert an NDC code to a FHIR Medication resource",
                    parameters={
                        "type": "object",
                        "properties": {
                            "ndc_code": {
                                "type": "string",
                                "description": "National Drug Code to convert"
                            }
                        },
                        "required": ["ndc_code"]
                    }
                )
            ),
            
            # Prompt Templates
            Resource(
                uri="pharmacy/prompt_templates",
                name="Pharmacy Prompt Templates",
                description="Get structured prompt templates for pharmacy informatics tasks",
                function=FunctionDef(
                    name="list_templates",
                    description="Get a list of available pharmacy prompt templates",
                    parameters={
                        "type": "object",
                        "properties": {}
                    }
                )
            ),
            
            # Get Specific Prompt Template
            Resource(
                uri="pharmacy/get_template",
                name="Get Pharmacy Prompt Template",
                description="Get a specific pharmacy prompt template by ID",
                function=FunctionDef(
                    name="get_prompt_template",
                    description="Get a prompt template by its ID",
                    parameters={
                        "type": "object",
                        "properties": {
                            "template_id": {
                                "type": "string",
                                "description": "ID of the template to retrieve"
                            }
                        },
                        "required": ["template_id"]
                    }
                )
            ),
            
            # Format Prompt Template
            Resource(
                uri="pharmacy/format_template",
                name="Format Pharmacy Prompt Template",
                description="Format a pharmacy prompt template with parameters",
                function=FunctionDef(
                    name="format_prompt",
                    description="Format a prompt template with the provided parameters",
                    parameters={
                        "type": "object",
                        "properties": {
                            "template_id": {
                                "type": "string",
                                "description": "ID of the template to format"
                            },
                            "parameters": {
                                "type": "object",
                                "description": "Parameters to fill in the template"
                            }
                        },
                        "required": ["template_id", "parameters"]
                    }
                )
            ),
            
            # PubMed Articles
            Resource(
                uri="pubmed/article_search",
                name="PubMed Article Search",
                description="Search for medical research articles on PubMed",
                function=FunctionDef(
                    name="search_articles",
                    description="Search for medical research articles by keyword, author, or topic",
                    parameters={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search terms, keywords, or author names"
                            },
                            "date_range": {
                                "type": "string",
                                "description": "Optional date range (e.g., '2020-2023')"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 5
                            }
                        },
                        "required": ["query"]
                    }
                )
            ),
            
            # Clinical Trials
            Resource(
                uri="clinicaltrials/search",
                name="ClinicalTrials.gov Search",
                description="Search for clinical trials by condition, intervention, or location",
                function=FunctionDef(
                    name="search_trials",
                    description="Search for active or completed clinical trials",
                    parameters={
                        "type": "object",
                        "properties": {
                            "condition": {
                                "type": "string",
                                "description": "Medical condition or disease"
                            },
                            "intervention": {
                                "type": "string",
                                "description": "Treatment, drug, or procedure being studied"
                            },
                            "status": {
                                "type": "string", 
                                "description": "Trial status (e.g., 'recruiting', 'completed')"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results to return",
                                "default": 5
                            }
                        },
                        "required": ["condition"]
                    }
                )
            )
        ]
        
        # In a real implementation, we might implement pagination
        # For now, we return all resources at once
        return {
            "resources": resources,
            "has_more": False,
            "cursor": ""
        }
    except Exception as e:
        logger.error(f"Error in list_resources: {e}")
        return Response(
            content=json.dumps({"error": MCPError(message=str(e)).dict()}),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            media_type="application/json"
        )

@router.post("/resources/{uri}")
async def get_resource(request: Request, uri: str):
    """
    Get detailed information about a specific resource.
    
    This endpoint follows the MCP protocol for resource information retrieval.
    """
    try:
        # URI is now passed as a path parameter
        logger.info(f"Getting resource details for URI: {uri}")
        
        # Now we look for the resource in our list of resources
        # For now, we'll return a placeholder with the URI
        return {"uri": uri, "name": f"Resource {uri}", "description": f"Details for {uri}"}
    except Exception as e:
        logger.error(f"Error in get_resource: {e}")
        return Response(
            content=json.dumps({"error": MCPError(message=str(e)).dict()}),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            media_type="application/json"
        )

@router.post("/resources/{uri}/execute")
async def execute_resource(request: Request, uri: str):
    """
    Execute a resource function with the provided arguments.
    
    This endpoint routes the request to the appropriate medical data provider.
    """
    try:
        body = await request.json()
        arguments = body.get("arguments", {})
        
        logger.info(f"Executing resource: {uri} with arguments: {arguments}")
        
        # Route the request to the appropriate handler based on URI
        if uri == "fda/drug/search":
            # Import here to avoid circular import
            from app.routes.fda.ndc_routes import search_ndc_compact
            result = await search_ndc_compact(**arguments)
            return {"result": result}
            
        elif uri == "fda/label/data":
            # Import here to avoid circular import
            from app.routes.fda.label_routes import search_label_data
            result = await search_label_data(**arguments)
            return {"result": result}
            
        elif uri == "fda/drug_lookup":
            result = await fda.search_medication(**arguments)
            return {"result": result}
            
        elif uri == "pubmed/article_search":
            result = await pubmed.search_articles(**arguments)
            return {"result": result}
            
        elif uri == "clinicaltrials/search":
            result = await trials.search_trials(**arguments)
            return {"result": result}
            
        # Pharmacy Informatics Tools
        elif uri == "pharmacy/ndc_lookup":
            result = await ndc.enhanced_ndc_lookup(**arguments)
            return {"result": result}
            
        elif uri == "pharmacy/rxnorm_mapping":
            result = await rxnorm.rxnorm_mapping(**arguments)
            return {"result": result}
            
        elif uri == "pharmacy/order_set_evidence":
            result = await evidence.get_evidence_for_order_set(**arguments)
            return {"result": result}
            
        elif uri == "pharmacy/formulary_alternatives":
            result = await formulary.analyze_formulary_alternatives(**arguments)
            return {"result": result}
            
        elif uri == "pharmacy/fhir_medication":
            result = await fhir.generate_fhir_medication_resource(**arguments)
            return {"result": result}
            
        elif uri == "pharmacy/ndc_to_fhir":
            result = await fhir.convert_ndc_to_fhir(**arguments)
            return {"result": result}
            
        # Prompt Templates
        elif uri == "pharmacy/prompt_templates":
            result = pharmacy_templates.list_templates()
            return {"result": result}
            
        elif uri == "pharmacy/get_template":
            result = pharmacy_templates.get_prompt_template(**arguments)
            return {"result": result}
            
        elif uri == "pharmacy/format_template":
            # Extract parameters from the arguments
            template_id = arguments.pop("template_id")
            parameters = arguments.pop("parameters")
            result = pharmacy_templates.format_prompt(template_id, **parameters)
            return {"result": result}
            
        else:
            return Response(
                content=json.dumps({"error": MCPError(message=f"Resource not found: {uri}").dict()}),
                status_code=status.HTTP_404_NOT_FOUND,
                media_type="application/json"
            )
    except Exception as e:
        logger.error(f"Error in execute_resource: {e}")
        return Response(
            content=json.dumps({"error": MCPError(message=str(e)).dict()}),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            media_type="application/json"
        )
