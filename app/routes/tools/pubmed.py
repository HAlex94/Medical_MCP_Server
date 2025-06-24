"""
PubMed Article Search API Module

This module provides functions to query PubMed for medical research articles.
It uses the NCBI E-utilities API to search and retrieve article information.
"""
import logging
from typing import Dict, Any, List, Optional
from app.utils.api_clients import make_request, get_api_key

logger = logging.getLogger(__name__)

# NCBI E-utilities API endpoints
NCBI_API_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ESEARCH_ENDPOINT = f"{NCBI_API_BASE}/esearch.fcgi"
ESUMMARY_ENDPOINT = f"{NCBI_API_BASE}/esummary.fcgi"
EFETCH_ENDPOINT = f"{NCBI_API_BASE}/efetch.fcgi"

async def search_articles(query: str, date_range: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    """
    Search for medical research articles on PubMed.
    
    Args:
        query: Search terms, keywords, or author names
        date_range: Optional date range (e.g., '2020-2023')
        limit: Maximum number of results to return
        
    Returns:
        Dictionary containing article information
    """
    logger.info(f"Searching PubMed for: {query}")
    
    # Get NCBI API key if available
    ncbi_api_key = get_api_key("NCBI_API_KEY")
    
    try:
        # Build date range filter if provided
        date_filter = ""
        if date_range:
            # Parse date range (format expected: "YYYY-YYYY")
            try:
                start_year, end_year = date_range.split("-")
                date_filter = f" AND {start_year}:{end_year}[pdat]"
            except ValueError:
                logger.warning(f"Invalid date range format: {date_range}. Expected format: 'YYYY-YYYY'")
                
        # Step 1: Search for articles that match the query
        search_params = {
            "db": "pubmed",
            "term": f"{query}{date_filter}",
            "retmax": limit,
            "retmode": "json",
            "sort": "relevance",
        }
        
        # Add API key to params if available (NCBI accepts it as a parameter)
        if ncbi_api_key:
            search_params["api_key"] = ncbi_api_key
        
        search_response = await make_request(
            url=ESEARCH_ENDPOINT,
            params=search_params,
            method="GET"
        )
        
        if not search_response or "esearchresult" not in search_response:
            return {
                "status": "error",
                "message": "No results found in PubMed",
                "query": query,
                "articles": []
            }
            
        # Extract article IDs from search results
        article_ids = search_response["esearchresult"].get("idlist", [])
        
        if not article_ids:
            return {
                "status": "error",
                "message": "No article IDs found in PubMed search results",
                "query": query,
                "articles": []
            }
            
        # Step 2: Get article summaries using article IDs
        summary_params = {
            "db": "pubmed",
            "id": ",".join(article_ids),
            "retmode": "json",
        }
        
        # Add API key to params if available
        if ncbi_api_key:
            summary_params["api_key"] = ncbi_api_key
        
        summary_response = await make_request(
            url=ESUMMARY_ENDPOINT,
            params=summary_params,
            method="GET"
        )
        
        if not summary_response or "result" not in summary_response:
            return {
                "status": "error",
                "message": "Failed to retrieve article summaries from PubMed",
                "query": query,
                "articles": []
            }
            
        # Process and extract relevant article information
        articles = []
        result_dict = summary_response["result"]
        
        # Skip the uids entry
        for article_id in article_ids:
            if article_id not in result_dict:
                continue
                
            article_data = result_dict[article_id]
            
            # Extract authors (first 3)
            authors = article_data.get("authors", [])
            author_names = []
            for author in authors[:3]:
                if "name" in author:
                    author_names.append(author["name"])
            
            # Format publication date
            pub_date = article_data.get("pubdate", "No date available")
            
            # Create article entry
            article = {
                "article_id": article_id,
                "title": article_data.get("title", "No title available"),
                "authors": ", ".join(author_names) + ("..." if len(authors) > 3 else ""),
                "journal": article_data.get("fulljournalname", article_data.get("source", "Unknown journal")),
                "publication_date": pub_date,
                "abstract": article_data.get("abstract", "No abstract available"),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{article_id}/",
                "doi": article_data.get("elocationid", "No DOI available"),
            }
            articles.append(article)
        
        return {
            "status": "success",
            "message": f"Found {len(articles)} articles matching '{query}'",
            "query": query,
            "articles": articles
        }
        
    except Exception as e:
        logger.error(f"Error searching PubMed: {e}")
        return {
            "status": "error",
            "message": f"Error searching PubMed: {str(e)}",
            "query": query,
            "articles": []
        }
