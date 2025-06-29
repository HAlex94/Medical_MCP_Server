"""
Unit tests for DailyMed HTML parsing functionality.
"""

import pytest
from bs4 import BeautifulSoup
from app.utils.dailymed.parse import extract_basic_info, extract_full_sections, extract_tables

@pytest.fixture
def sample_drug_html():
    """Return a BeautifulSoup object with sample drug HTML."""
    return BeautifulSoup("""
    <html>
      <head>
        <title>ASPIRIN (acetylsalicylic acid) tablet</title>
      </head>
      <body>
        <h1 class="drug-title">ASPIRIN (acetylsalicylic acid) tablet</h1>
        <div class="manufacturer">Bayer Healthcare LLC</div>
        
        <div class="Section">
          <h2 class="Section-title">INDICATIONS AND USAGE</h2>
          <p>Aspirin is indicated for the temporary relief of minor aches and pains.</p>
          <p>Adults and children 12 years of age and over: Take 1 or 2 tablets every 4 to 6 hours as needed.</p>
        </div>
        
        <div class="Section">
          <h2 class="Section-title">CONTRAINDICATIONS</h2>
          <p>Do not use if you are allergic to aspirin or any other pain reliever/fever reducer.</p>
        </div>
        
        <div class="Section">
          <h2 class="Section-title">DOSAGE AND ADMINISTRATION</h2>
          <table>
            <tr>
              <th>Age</th>
              <th>Dose</th>
              <th>Frequency</th>
            </tr>
            <tr>
              <td>Adults and children 12 years and over</td>
              <td>1-2 tablets</td>
              <td>Every 4-6 hours as needed</td>
            </tr>
            <tr>
              <td>Children under 12 years</td>
              <td>Consult a doctor</td>
              <td>N/A</td>
            </tr>
          </table>
        </div>
        
        <div>
          <p>Set ID: 12345-678-90</p>
          <p>NDC Code: 12345-678-90</p>
        </div>
        
        <div>
          <a href="drug_label.pdf">PDF Download</a>
          <a href="drug_data.xml">XML Data</a>
        </div>
      </body>
    </html>
    """, "html.parser")

def test_extract_basic_info(sample_drug_html):
    """Test extraction of basic drug information."""
    info = extract_basic_info(sample_drug_html)
    
    assert info.get("title") == "ASPIRIN (acetylsalicylic acid) tablet"
    assert info.get("manufacturer") == "Bayer Healthcare LLC"
    assert "downloads" in info
    assert len(info["downloads"]) == 2, "Should extract 2 download links"

def test_extract_full_sections(sample_drug_html):
    """Test extraction of full text sections."""
    sections = extract_full_sections(sample_drug_html)
    
    assert len(sections) == 3, "Should extract 3 sections"
    assert "INDICATIONS AND USAGE" in sections
    assert "CONTRAINDICATIONS" in sections
    assert "DOSAGE AND ADMINISTRATION" in sections
    
    # Check that content was properly extracted
    assert "temporary relief of minor aches" in sections["INDICATIONS AND USAGE"]
    assert "allergic to aspirin" in sections["CONTRAINDICATIONS"]

def test_extract_tables(sample_drug_html):
    """Test extraction of tables from sections."""
    tables = extract_tables(sample_drug_html)
    
    assert len(tables) == 1, "Should extract 1 section with tables"
    assert "DOSAGE AND ADMINISTRATION" in tables
    
    dosage_tables = tables["DOSAGE AND ADMINISTRATION"]
    assert len(dosage_tables) == 1, "Should have 1 table in the section"
    
    # Check table content
    table = dosage_tables[0]
    assert len(table) == 2, "Table should have 2 data rows"
    assert "Age" in table[0], "First column should be Age"
    assert "Adults and children 12 years and over" in table[0]["Age"]
    assert "1-2 tablets" in table[0]["Dose"]
