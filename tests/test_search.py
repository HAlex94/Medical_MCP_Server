"""
Unit tests for DailyMed search functionality.
"""

import pytest
from app.utils.dailymed.models import DrugResult

# Common medications that should reliably return search results
COMMON_DRUGS = [
    "Lipitor",      # Cholesterol medication
    "Synthroid",    # Thyroid medication
    "Proair",       # Asthma inhaler
    "Ventolin",     # Asthma inhaler
    "Delasone",     # Prednisone, steroid
    "Amoxil",       # Amoxicillin, antibiotic
    "Neurontin",    # Gabapentin, nerve pain
    "Prinivil"      # Lisinopril, blood pressure
]

@pytest.mark.parametrize("drug_name", COMMON_DRUGS)
def test_search_returns_results(client, drug_name):
    """Test that common drugs return at least one search result."""
    results = client.search(drug_name, limit=3)
    
    # We expect at least 1 result for these very common drugs
    assert isinstance(results, list)
    assert len(results) >= 1, f"No results for {drug_name}"
    
    first = results[0]
    assert isinstance(first, DrugResult), f"Result should be a DrugResult object, got {type(first)}"
    assert first.drug_name, f"Missing drug_name for {drug_name}"
    assert first.url and first.url.startswith("http"), f"Invalid URL for {drug_name}: {first.url}"

def test_search_with_nonexistent_drug(client):
    """Test search behavior with a nonsensical drug name."""
    # Using a nonsensical string that shouldn't match any real drug
    results = client.search("xyznonexistentdrugabc123", limit=3)
    
    # Should return a list (empty or not) but not error
    assert isinstance(results, list)
    # Check that if results are found, they're properly structured
    if results:
        for result in results:
            assert hasattr(result, 'drug_name')
            assert hasattr(result, 'url')
            # The URL should be valid
            assert result.url and result.url.startswith('http')
    
    # Even if DailyMed returns results, our test passes if the code handles it properly

def test_search_limit_respected(client):
    """Test that the limit parameter is respected."""
    # Search for a common drug that will have many results
    for limit in [1, 3, 5]:
        results = client.search("aspirin", limit=limit)
        assert len(results) <= limit, f"Search returned {len(results)} results, exceeding limit {limit}"
