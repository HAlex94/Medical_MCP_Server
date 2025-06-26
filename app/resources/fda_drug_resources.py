from app.models.fda_resources import DrugSearchParams
from app.routes.fda.ndc_routes import search_ndc_compact

FDA_DRUG_RESOURCES = [
    {
        "uri": "fda/drug/search",
        "name": "Search FDA Drug Products",
        "description": "Search for drug products in the FDA NDC Directory with pagination and compact results to avoid response size issues",
        "operation": {
            "parameters_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Brand or generic name of the drug"},
                    "manufacturer": {"type": "string", "description": "Name of the manufacturer"},
                    "active_ingredient": {"type": "string", "description": "Active ingredient in the drug"},
                    "ndc": {"type": "string", "description": "National Drug Code"},
                    "limit": {"type": "integer", "default": 10, "description": "Maximum number of results to return"},
                    "skip": {"type": "integer", "default": 0, "description": "Number of results to skip for pagination"}
                }
            },
            "function": search_ndc_compact
        }
    }
]
