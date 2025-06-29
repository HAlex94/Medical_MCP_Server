"""
Tests for the DailyMed fallback mechanism when OpenFDA data is unavailable.

These tests verify that when drug information is not available in the FDA database,
the system correctly falls back to DailyMed data sources.
"""

import pytest
import requests
import logging
from typing import Dict, Any, List
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://medical-mcp-server.onrender.com"
DAILYMED_FALLBACK_ENDPOINT = f"{BASE_URL}/fda/dailymed-fallback"
DRUG_SEARCH_ENDPOINT = f"{BASE_URL}/fda/drug-search"

# Test drugs that might need DailyMed fallback
# Choose some less common medications or those that might not be in OpenFDA
TEST_FALLBACK_DRUGS = [
    "Orphenadrine",  # Muscle relaxant
    "Cilostazol",    # Blood thinner
    "Ethosuximide",  # Anti-epileptic
    "Leflunomide",   # Immunosuppressant
]

@pytest.mark.integration
@pytest.mark.parametrize("drug_name", TEST_FALLBACK_DRUGS)
def test_dailymed_fallback_search(drug_name):
    """Test that the DailyMed fallback search returns results for test drugs."""
    response = requests.get(
        DAILYMED_FALLBACK_ENDPOINT,
        params={"name": drug_name}
    )
    
    # Check if the endpoint exists yet
    if response.status_code == 404:
        pytest.skip("DailyMed fallback endpoint not yet deployed")
    
    assert response.status_code == 200, f"Failed to get DailyMed fallback data for {drug_name}"
    data = response.json()
    
    # Ensure the basic structure of the response
    assert isinstance(data, list), "Response should be a list of search results"
    
    # We may not always get results for every drug, but we should check the structure when we do
    if len(data) > 0:
        first_result = data[0]
        assert "title" in first_result, "Missing title in search result"
        assert "setid" in first_result, "Missing setid in search result"
        assert "spl_version" in first_result, "Missing spl_version in search result"
        assert "source" in first_result and first_result["source"] == "dailymed", "Missing source field"
        
        # Check the title contains the drug name (case-insensitive)
        if "title" in first_result and first_result["title"]:
            assert re.search(drug_name, first_result["title"], re.IGNORECASE), \
                f"Drug name {drug_name} not found in title: {first_result['title']}"
                
        logger.info(f"Found {len(data)} DailyMed results for {drug_name}")

@pytest.mark.integration
def test_dailymed_spl_data():
    """Test retrieving SPL (Structured Product Labeling) data from DailyMed."""
    # First search for a drug to get its setid
    test_drug = "Leflunomide"  # Common drug that should be available
    
    response = requests.get(
        DAILYMED_FALLBACK_ENDPOINT,
        params={"name": test_drug}
    )
    
    # Check if the endpoint exists yet
    if response.status_code == 404:
        pytest.skip("DailyMed fallback endpoint not yet deployed")
        
    if response.status_code == 200:
        data = response.json()
        if len(data) > 0:
            setid = data[0].get("setid")
            
            if setid:
                # Now retrieve the SPL data using the setid
                spl_response = requests.get(
                    f"{DAILYMED_FALLBACK_ENDPOINT}/spl/{setid}"
                )
                
                # Check if this specific endpoint is implemented
                if spl_response.status_code == 404:
                    pytest.skip("DailyMed SPL data endpoint not yet deployed")
                
                assert spl_response.status_code == 200, f"Failed to get SPL data for setid {setid}"
                spl_data = spl_response.json()
                
                # Check basic structure of SPL data
                assert "setId" in spl_data, "Missing setId in SPL data"
                assert "data" in spl_data, "Missing data in SPL response"
                
                # The data should contain structured information about the drug
                data_fields = spl_data["data"]
                assert isinstance(data_fields, dict), "SPL data should be a dictionary"
                
                # Check for some common sections in SPL data
                important_sections = [
                    "indications_and_usage",
                    "dosage_and_administration",
                    "contraindications",
                    "warnings",
                    "adverse_reactions",
                    "drug_interactions"
                ]
                
                # At least some of these sections should be present
                sections_found = sum(1 for section in important_sections if section in data_fields)
                assert sections_found > 0, "No important sections found in SPL data"
                
                logger.info(f"Successfully retrieved SPL data for {test_drug} with setid {setid}")
            else:
                pytest.skip("No setid found for the test drug")
        else:
            pytest.skip("No search results found for the test drug")

@pytest.mark.integration
def test_drug_search_with_fallback():
    """
    Test that the main drug search endpoint falls back to DailyMed
    when FDA data is not available.
    """
    # Try with a drug that might need fallback
    test_drugs = ["Pentosan", "Nitazoxanide", "Riluzole"]
    
    for drug in test_drugs:
        response = requests.get(
            DRUG_SEARCH_ENDPOINT,
            params={"name": drug, "use_fallback": "true"}
        )
        
        # Check if the endpoint exists
        if response.status_code == 404:
            pytest.skip("Drug search endpoint with fallback not yet deployed")
        
        assert response.status_code == 200, f"Failed to get drug search results for {drug}"
        data = response.json()
        
        # Check response structure
        assert "results" in data, "Missing results in response"
        assert "sources_used" in data, "Missing sources_used in response"
        
        # If we got results
        if data["results"] and len(data["results"]) > 0:
            # Check if any results are from fallback
            fallback_results = [r for r in data["results"] if r.get("source") == "dailymed"]
            
            # Log information about results for debugging
            logger.info(f"Drug: {drug}")
            logger.info(f"Total results: {len(data['results'])}")
            logger.info(f"Sources used: {data.get('sources_used', [])}")
            logger.info(f"DailyMed fallback results: {len(fallback_results)}")
            
            # We don't force there to be fallback results, as some drugs might be found in FDA
            # But we verify the structure of what's returned
            if fallback_results:
                first_fallback = fallback_results[0]
                assert "brand_name" in first_fallback or "generic_name" in first_fallback, \
                    "Missing drug name fields in fallback result"
                assert "source" in first_fallback and first_fallback["source"] == "dailymed", \
                    "Fallback result should have source=dailymed"
            
            # If we found valid results, no need to test the other drugs
            if data["results"]:
                break


@pytest.mark.integration
def test_forced_dailymed_fallback():
    """Test forcing the use of DailyMed by skipping OpenFDA"""

    # Make request to the drug search endpoint with OpenFDA skipped
    response = requests.get(
        DRUG_SEARCH_ENDPOINT, 
        params={"name": "Lipitor", "skip_openfda": "true"}
    )
    
    # Check if the endpoint exists
    if response.status_code == 404:
        pytest.skip("Drug search endpoint with fallback not yet deployed")
    
    assert response.status_code == 200, "Expected 200 response for forced fallback"
    
    # Verify the response structure and that DailyMed was used
    data = response.json()
    sources = data.get("sources_used", [])
    
    # When skipping OpenFDA, DailyMed should be the source
    assert "dailymed" in sources, "DailyMed should be used when OpenFDA is skipped"
    assert "openfda" not in sources, "OpenFDA should not be used when skipped"
    
    # Verify we have results from DailyMed
    dailymed_results = [r for r in data["results"] if r.get("source") == "dailymed"]
    if dailymed_results:
        logger.info(f"Forced DailyMed fallback successful with {len(dailymed_results)} results")
    else:
        logger.warning("Forced DailyMed fallback did not return any results")

@pytest.mark.integration
def test_fallback_without_openfda_data():
    """Test that fallback mechanism works when OpenFDA returns no results."""
    # Try with a rare/unusual drug name that likely won't be in OpenFDA
    test_drug = "Cenegermin"  # Rare medication for neurotrophic keratitis
    
    response = requests.get(
        DRUG_SEARCH_ENDPOINT,
        params={
            "name": test_drug, 
            "use_fallback": True,
            "skip_openfda": True  # Force using fallback mechanism
        }
    )
    
    # Check if the endpoint exists
    if response.status_code == 404:
        pytest.skip("Drug search endpoint with fallback not yet deployed")
        
    assert response.status_code == 200
    data = response.json()
    
    # Check basic structure
    assert "results" in data, "Missing results in response"
    
    # We may or may not find this specific drug, but if results are returned,
    # they should have the correct structure and come from DailyMed
    if data["results"] and len(data["results"]) > 0:
        for result in data["results"]:
            assert "source" in result, "Missing source field in result"
            assert result["source"] == "dailymed", f"Expected source=dailymed but got {result.get('source')}"
