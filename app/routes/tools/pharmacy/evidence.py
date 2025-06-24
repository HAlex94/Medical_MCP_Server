"""
Evidence-Based Order Set Builder Module

This module provides tools for retrieving evidence-based recommendations for
clinical conditions to support the creation of order sets in EHR systems.
"""
import logging
from typing import Dict, Any, List, Optional
from app.utils.api_clients import make_request, get_api_key
from app.routes.tools import pubmed

logger = logging.getLogger(__name__)

# API endpoints for evidence-based guidelines
NIH_GUIDELINES_API = "https://clinicalguidelines.gov/api/v1/guideline"
AHRQ_GUIDELINES_API = "https://effectivehealthcare.ahrq.gov/api/collections/systematic-reviews"

async def get_evidence_for_order_set(
    condition: str,
    intervention_type: str = "medication"
) -> Dict[str, Any]:
    """
    Retrieve evidence-based recommendations for specific clinical conditions
    to support the creation of order sets in EHR systems.
    
    Args:
        condition: The clinical condition or disease
        intervention_type: Type of intervention ("medication", "lab", "imaging")
        
    Returns:
        Dictionary containing evidence-based recommendations
    """
    logger.info(f"Getting evidence-based recommendations for {condition} ({intervention_type})")
    
    try:
        results = {
            "status": "processing",
            "condition": condition,
            "intervention_type": intervention_type,
            "pubmed_evidence": [],
            "clinical_guidelines": [],
            "recommendations": []
        }
        
        # Step 1: Get recent research articles from PubMed
        pubmed_query = f"{condition} AND {intervention_type}"
        if intervention_type == "medication":
            pubmed_query += " AND (therapy OR treatment OR management)"
        elif intervention_type == "lab":
            pubmed_query += " AND (laboratory OR diagnostic OR biomarker OR monitoring)"
        elif intervention_type == "imaging":
            pubmed_query += " AND (imaging OR radiology OR diagnostic)"
            
        # Add filter for higher-quality studies
        pubmed_query += " AND (guideline OR \"systematic review\" OR \"clinical trial\" OR \"practice guideline\")"
        
        pubmed_response = await pubmed.search_articles(pubmed_query, limit=5)
        
        if pubmed_response.get("status") == "success":
            results["pubmed_evidence"] = pubmed_response.get("articles", [])
        
        # Step 2: Get clinical guidelines from NIH repository
        guidelines_params = {
            "keyword": condition
        }
        
        guidelines_response = await make_request(
            url=NIH_GUIDELINES_API,
            params=guidelines_params,
            method="GET"
        )
        
        if guidelines_response and "guidelines" in guidelines_response:
            guidelines = guidelines_response.get("guidelines", [])
            for guideline in guidelines[:5]:  # Limit to first 5 guidelines
                results["clinical_guidelines"].append({
                    "title": guideline.get("title", "Unknown title"),
                    "organization": guideline.get("organization", "Unknown organization"),
                    "publication_date": guideline.get("publicationDate", "Unknown date"),
                    "url": guideline.get("url", ""),
                    "summary": guideline.get("abstractText", "No summary available")
                })
        
        # Step 3: Create integrated evidence-based recommendations
        # This combines the PubMed literature and clinical guidelines
        
        # For each intervention type, extract relevant recommendations
        if intervention_type == "medication":
            medication_recs = await extract_medication_recommendations(
                results["pubmed_evidence"], 
                results["clinical_guidelines"]
            )
            results["recommendations"] = medication_recs
        elif intervention_type == "lab":
            lab_recs = await extract_lab_recommendations(
                results["pubmed_evidence"], 
                results["clinical_guidelines"]
            )
            results["recommendations"] = lab_recs
        elif intervention_type == "imaging":
            imaging_recs = await extract_imaging_recommendations(
                results["pubmed_evidence"], 
                results["clinical_guidelines"]
            )
            results["recommendations"] = imaging_recs
        
        # Final result with success status
        results["status"] = "success"
        results["message"] = f"Found {len(results['recommendations'])} evidence-based recommendations for {condition} ({intervention_type})"
        
        return results
    
    except Exception as e:
        logger.error(f"Error getting evidence for order set: {e}")
        return {
            "status": "error",
            "message": f"Error retrieving evidence-based recommendations: {str(e)}",
            "condition": condition,
            "intervention_type": intervention_type,
            "recommendations": []
        }

async def extract_medication_recommendations(articles, guidelines) -> List[Dict[str, Any]]:
    """Extract medication recommendations from articles and guidelines"""
    recommendations = []
    
    # This would ideally use NLP or a medical knowledge base
    # For now we'll create a simplified structure with references to the sources
    
    # Process articles first
    for idx, article in enumerate(articles):
        title = article.get("title", "").lower()
        abstract = article.get("abstract", "").lower()
        
        # Skip if not relevant to recommendations
        if not any(term in title + abstract for term in ["recommend", "guideline", "consensus", "treatment", "therapy"]):
            continue
            
        # Extract key info from title and abstract
        recommendation = {
            "intervention": "Medication",
            "description": f"Based on {article.get('title')}",
            "evidence_level": "Research article",
            "source": f"PubMed article - {article.get('url', '')}",
            "date": article.get('publication_date', ''),
        }
        recommendations.append(recommendation)
    
    # Process guidelines
    for guideline in guidelines:
        recommendation = {
            "intervention": "Medication",
            "description": f"Follow {guideline.get('organization')} guidelines: {guideline.get('title')}",
            "evidence_level": "Clinical Guideline",
            "source": guideline.get('url', ''),
            "date": guideline.get('publication_date', ''),
        }
        recommendations.append(recommendation)
    
    return recommendations

async def extract_lab_recommendations(articles, guidelines) -> List[Dict[str, Any]]:
    """Extract lab test recommendations from articles and guidelines"""
    recommendations = []
    
    # Process articles
    for article in articles:
        title = article.get("title", "").lower()
        abstract = article.get("abstract", "").lower()
        
        # Skip if not relevant to lab recommendations
        if not any(term in title + abstract for term in ["test", "laboratory", "diagnostic", "biomarker", "monitor"]):
            continue
            
        recommendation = {
            "intervention": "Laboratory Test",
            "description": f"Based on {article.get('title')}",
            "evidence_level": "Research article",
            "source": f"PubMed article - {article.get('url', '')}",
            "date": article.get('publication_date', ''),
        }
        recommendations.append(recommendation)
    
    # Process guidelines
    for guideline in guidelines:
        recommendation = {
            "intervention": "Laboratory Test",
            "description": f"Follow {guideline.get('organization')} guidelines: {guideline.get('title')}",
            "evidence_level": "Clinical Guideline",
            "source": guideline.get('url', ''),
            "date": guideline.get('publication_date', ''),
        }
        recommendations.append(recommendation)
    
    return recommendations

async def extract_imaging_recommendations(articles, guidelines) -> List[Dict[str, Any]]:
    """Extract imaging recommendations from articles and guidelines"""
    recommendations = []
    
    # Process articles
    for article in articles:
        title = article.get("title", "").lower()
        abstract = article.get("abstract", "").lower()
        
        # Skip if not relevant to imaging recommendations
        if not any(term in title + abstract for term in ["imaging", "radiology", "scan", "ultrasound", "mri", "ct", "x-ray"]):
            continue
            
        recommendation = {
            "intervention": "Imaging",
            "description": f"Based on {article.get('title')}",
            "evidence_level": "Research article",
            "source": f"PubMed article - {article.get('url', '')}",
            "date": article.get('publication_date', ''),
        }
        recommendations.append(recommendation)
    
    # Process guidelines
    for guideline in guidelines:
        recommendation = {
            "intervention": "Imaging",
            "description": f"Follow {guideline.get('organization')} guidelines: {guideline.get('title')}",
            "evidence_level": "Clinical Guideline",
            "source": guideline.get('url', ''),
            "date": guideline.get('publication_date', ''),
        }
        recommendations.append(recommendation)
    
    return recommendations
