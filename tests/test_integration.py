"""
Integration tests for DailyMed API.

These tests make actual network calls to DailyMed and should be run separately.
"""

import pytest
import os
from pathlib import Path

# A smaller set of medications for integration testing
INTEGRATION_DRUGS = [
    "Lipitor",     # Common
    "Jardiance",   # Less common
    "Trikafta"     # Specialty
]

@pytest.mark.integration
@pytest.mark.parametrize("drug_name", INTEGRATION_DRUGS)
def test_get_drug_by_name_integration(client, drug_name, tmp_path):
    """Test the entire pipeline from search to detailed drug data retrieval."""
    drug_data = client.get_drug_by_name(drug_name)
    
    # Basic assertions to ensure data was retrieved correctly
    assert not hasattr(drug_data, 'error') or not drug_data.error, f"Error for {drug_name}: {drug_data.error if hasattr(drug_data, 'error') else None}"
    assert drug_data.title, f"Title missing for {drug_name}"
    assert isinstance(drug_data.full_sections, dict), f"Sections should be a dict for {drug_name}"
    assert len(drug_data.full_sections) > 0, f"No sections found for {drug_name}"
    
    # Check for key required sections
    important_section_found = False
    key_sections = [
        "INDICATIONS AND USAGE",
        "DOSAGE AND ADMINISTRATION", 
        "CONTRAINDICATIONS",
        "WARNINGS AND PRECAUTIONS",
        "ADVERSE REACTIONS",
        "DESCRIPTION"
    ]
    
    for section in drug_data.full_sections.keys():
        for key_section in key_sections:
            if key_section in section.upper():
                important_section_found = True
                break
    
    assert important_section_found, f"No important sections found for {drug_name}. Found sections: {list(drug_data.full_sections.keys())}"

@pytest.mark.integration
def test_extract_specific_section(client):
    """Test the section extraction helper function."""
    # Get data for a drug that definitely has dosage information
    drug_data = client.get_drug_by_name("Aspirin")
    
    # Use the client's helper method to extract a specific section
    dosage_section = client.extract_section(drug_data, ["dosage", "administration"])
    
    # Should find something related to dosage
    assert dosage_section, "Dosage section not found"
    assert any(keyword in dosage_section.lower() for keyword in ["tablet", "dose", "take", "mg"]), \
           "Dosage section doesn't contain expected keywords"

@pytest.mark.integration
def test_extract_tables_from_section(client):
    """Test the table extraction helper function."""
    # Find a drug known to have tables
    drug_data = client.get_drug_by_name("Lipitor")
    
    # Try to extract tables from clinical pharmacology or dosage sections
    tables = client.extract_tables_from_section(
        drug_data, 
        ["clinical", "pharmacology", "dosage", "administration"]
    )
    
    # Just check if we got any tables - this is primarily a smoke test
    # The exact table structure will vary by drug
    assert isinstance(tables, list), "Should return a list of tables"
