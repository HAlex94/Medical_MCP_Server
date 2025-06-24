"""
ClinicalTrials.gov Search API Module

This module provides functions to query the ClinicalTrials.gov database for information
on clinical trials for various medical conditions.
"""
import logging
from typing import Dict, Any, List, Optional
from app.utils.api_clients import make_request, get_api_key

logger = logging.getLogger(__name__)

# ClinicalTrials.gov API endpoints
CLINICALTRIALS_API_BASE = "https://clinicaltrials.gov/api/query/study_fields"

async def search_trials(condition: str, 
                        intervention: Optional[str] = None, 
                        status: Optional[str] = None, 
                        limit: int = 5) -> Dict[str, Any]:
    """
    Search for clinical trials by condition, intervention, or status.
    
    Args:
        condition: Medical condition or disease
        intervention: Treatment, drug, or procedure being studied (optional)
        status: Trial status (e.g., 'recruiting', 'completed') (optional)
        limit: Maximum number of results to return
        
    Returns:
        Dictionary containing clinical trial information
    """
    logger.info(f"Searching ClinicalTrials.gov for condition: {condition}")
    
    # Get API key if available (for future use if ClinicalTrials.gov adds API key support)
    ct_api_key = get_api_key("CLINICAL_TRIALS_API_KEY")
    
    try:
        # Build search expression
        expr = f"CONDITION:{condition}"
        if intervention:
            expr += f" AND INTERVENTION:{intervention}"
        if status:
            expr += f" AND STATUS:{status}"
            
        # Define fields to retrieve
        fields = [
            "NCTId", "BriefTitle", "OfficialTitle", "OverallStatus", 
            "StudyType", "Phase", "StartDate", "PrimaryCompletionDate", 
            "CompletionDate", "StudyFirstPostDate", "ResultsFirstPostDate",
            "Condition", "ConditionMeshTerm", "Intervention", "InterventionType",
            "InterventionMeshTerm", "EnrollmentCount", "LeadSponsorName",
            "BriefSummary", "DetailedDescription", "LocationFacility", 
            "LocationCity", "LocationState", "LocationCountry"
        ]
        
        # Set up the query parameters
        params = {
            "expr": expr,
            "fields": ",".join(fields),
            "min_rnk": 1,
            "max_rnk": limit,
            "fmt": "json",
        }
        
        # Make request to ClinicalTrials.gov API
        response = await make_request(
            url=CLINICALTRIALS_API_BASE,
            params=params,
            method="GET"
        )
        
        if not response or "StudyFieldsResponse" not in response:
            return {
                "status": "error",
                "message": "No results found in ClinicalTrials.gov database",
                "condition": condition,
                "trials": []
            }
            
        study_data = response["StudyFieldsResponse"]
        studies = study_data.get("StudyFields", [])
        
        if not studies:
            return {
                "status": "error",
                "message": f"No clinical trials found for condition: {condition}",
                "condition": condition,
                "trials": []
            }
            
        # Process and extract relevant clinical trial information
        trials = []
        for study in studies:
            # Helper function to safely get the first value from a field array
            def get_field(field_name):
                values = study.get(field_name, [])
                return values[0] if values else "Not available"
            
            # Helper function to safely get all values from a field array
            def get_all_fields(field_name):
                return study.get(field_name, ["Not available"])
            
            trial = {
                "nct_id": get_field("NCTId"),
                "title": get_field("BriefTitle"),
                "official_title": get_field("OfficialTitle"),
                "status": get_field("OverallStatus"),
                "phase": get_field("Phase"),
                "start_date": get_field("StartDate"),
                "completion_date": get_field("CompletionDate"),
                "conditions": get_all_fields("Condition"),
                "interventions": get_all_fields("Intervention"),
                "intervention_types": get_all_fields("InterventionType"),
                "enrollment": get_field("EnrollmentCount"),
                "sponsor": get_field("LeadSponsorName"),
                "summary": get_field("BriefSummary"),
                "locations": [
                    f"{facility}, {city}, {state}, {country}" 
                    for facility, city, state, country in zip(
                        get_all_fields("LocationFacility"),
                        get_all_fields("LocationCity"),
                        get_all_fields("LocationState"),
                        get_all_fields("LocationCountry")
                    )
                ],
                "url": f"https://clinicaltrials.gov/study/{get_field('NCTId')}",
            }
            trials.append(trial)
        
        return {
            "status": "success",
            "message": f"Found {len(trials)} clinical trials for '{condition}'",
            "condition": condition,
            "intervention": intervention,
            "status": status,
            "trials": trials
        }
        
    except Exception as e:
        logger.error(f"Error searching ClinicalTrials.gov: {e}")
        return {
            "status": "error",
            "message": f"Error searching ClinicalTrials.gov: {str(e)}",
            "condition": condition,
            "trials": []
        }
