"""
Pharmacy Informatics Prompt Templates

This module provides structured prompt templates for pharmacy informatics tasks
to ensure consistent, high-quality responses from LLMs.
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Template definitions
TEMPLATES = {
    "ehr_order_set_builder": {
        "name": "EHR Order Set Builder",
        "description": "Template for building evidence-based order sets in EHR systems",
        "template": """
For the clinical condition: {condition}
Purpose: Building evidence-based order sets in EHR

1. Summarize current standard of care from authoritative guidelines
2. List essential medication orders with appropriate defaults
   - Include specific medications with doses, routes, frequencies
   - Specify monitoring parameters and duration where applicable
3. Provide rationale for each component with evidence level
4. Identify quality metrics that this order set should support
5. Suggest alert/safety checks that should be incorporated

Additional context: {context}
        """.strip()
    },
    "system_configuration_analysis": {
        "name": "System Configuration Analysis",
        "description": "Template for analyzing medication system configurations",
        "template": """
For the following medication system configuration: {configuration}
Analyze:

1. Potential safety implications
   - Review alert fatigue potential
   - Assess for unintended consequences
2. Alignment with best practices and guidelines
   - ISMP best practices
   - Regulatory considerations (e.g., TJC, CMS)
3. Technical considerations for implementation
   - Integration points with existing systems
   - Data flow and dependencies
4. Suggested quality metrics to monitor post-implementation
5. Potential edge cases to consider

Additional context: {context}
        """.strip()
    },
    "ndc_product_analysis": {
        "name": "NDC/Product Information Analysis",
        "description": "Template for detailed analysis of medication product information",
        "template": """
For the medication product: {product_name}
NDC: {ndc}

Provide a comprehensive analysis:

1. Product composition and formulation
   - Active ingredients with strengths
   - Dosage form specifics
   - Inactive ingredients of clinical significance
2. Clinical applications
   - FDA-approved indications
   - Common off-label uses
   - Place in therapy
3. Supply chain considerations
   - Available package sizes
   - Storage requirements
   - Shelf life and stability
4. EHR integration considerations
   - Recommended build parameters
   - Dispensing considerations
   - MAR documentation specifics
5. Cost and formulary considerations
   - AWP/acquisition cost factors
   - Therapeutic alternatives comparison

Additional context: {context}
        """.strip()
    },
    "evidence_based_practice": {
        "name": "Evidence-Based Practice Review",
        "description": "Template for evaluating evidence for pharmacy practice decisions",
        "template": """
For the clinical question: {clinical_question}
Based on the retrieved literature: {literature_data}

1. Study design analysis
   - Study type and methodology assessment
   - Sample size and population characteristics
   - Primary and secondary endpoints
   - Statistical methods used
2. Key findings summary
   - Primary outcome results with confidence intervals
   - Secondary outcomes of clinical relevance  
   - Subgroup analyses of interest
3. Evidence quality assessment using GRADE criteria
   - Risk of bias
   - Inconsistency
   - Indirectness
   - Imprecision
   - Publication bias
4. Clinical applicability assessment
   - Relevance to current practice setting
   - External validity considerations
   - Implementation feasibility
5. Evidence-based recommendation
   - Strength of recommendation
   - Clinical practice impact
   - Necessary monitoring or follow-up

Additional context: {context}
        """.strip()
    },
    "formulary_decision_support": {
        "name": "Formulary Decision Support",
        "description": "Template for medication formulary management decisions",
        "template": """
For the medication under formulary consideration: {medication}
Therapeutic class: {therapeutic_class}

Provide formulary decision support:

1. Efficacy comparison within therapeutic class
   - Comparative trial data
   - Non-inferiority/superiority assessments
   - Relevant meta-analyses
2. Safety profile analysis
   - Common adverse effects
   - Black box warnings
   - Monitoring requirements
3. Cost effectiveness review
   - Acquisition cost comparison
   - Administration costs
   - Monitoring costs
   - Length of therapy considerations
4. Practical considerations
   - Dosing convenience
   - Storage requirements
   - Preparation requirements
   - Administration complexity
5. Population-specific considerations
   - Renal/hepatic dosing
   - Geriatric/pediatric considerations
   - Pregnancy/lactation implications
6. Recommended formulary position
   - Tier placement
   - Restriction criteria if applicable
   - Prior authorization criteria

Additional context: {context}
        """.strip()
    }
}

def get_prompt_template(template_id: str) -> Dict[str, Any]:
    """
    Get a prompt template by its ID.
    
    Args:
        template_id: Identifier for the template
        
    Returns:
        Dictionary containing template metadata and content
    """
    if template_id not in TEMPLATES:
        logger.warning(f"Template ID '{template_id}' not found")
        return {
            "status": "error",
            "message": f"Template '{template_id}' not found",
            "template": None
        }
    
    return {
        "status": "success",
        "template_id": template_id,
        "name": TEMPLATES[template_id]["name"],
        "description": TEMPLATES[template_id]["description"],
        "template": TEMPLATES[template_id]["template"]
    }

def list_templates() -> Dict[str, Any]:
    """
    List all available prompt templates.
    
    Returns:
        Dictionary containing list of templates with metadata
    """
    template_list = []
    
    for template_id, template in TEMPLATES.items():
        template_list.append({
            "id": template_id,
            "name": template["name"],
            "description": template["description"]
        })
    
    return {
        "status": "success",
        "count": len(template_list),
        "templates": template_list
    }

def format_prompt(template_id: str, **kwargs) -> Dict[str, Any]:
    """
    Format a prompt template with the provided parameters.
    
    Args:
        template_id: Identifier for the template
        **kwargs: Parameters to fill in the template
        
    Returns:
        Dictionary containing the formatted prompt
    """
    template_data = get_prompt_template(template_id)
    
    if template_data["status"] == "error":
        return template_data
    
    try:
        # Fill the template with provided parameters
        # Use empty string for missing parameters
        formatted_text = template_data["template"].format(**{k: kwargs.get(k, "") for k in kwargs})
        
        return {
            "status": "success",
            "template_id": template_id,
            "name": template_data["name"],
            "formatted_prompt": formatted_text
        }
    except KeyError as e:
        logger.error(f"Missing required parameter for template '{template_id}': {e}")
        return {
            "status": "error",
            "message": f"Missing required parameter for template '{template_id}': {str(e)}",
            "formatted_prompt": None
        }
    except Exception as e:
        logger.error(f"Error formatting template '{template_id}': {e}")
        return {
            "status": "error",
            "message": f"Error formatting template: {str(e)}",
            "formatted_prompt": None
        }
