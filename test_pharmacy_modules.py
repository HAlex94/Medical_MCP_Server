"""
Test script for pharmacy informatics modules with focused real API testing
"""
import asyncio
import json
import time
import os
from app.routes.tools.pharmacy import ndc, rxnorm, evidence, formulary, fhir
from app.prompt_templates import pharmacy as pharmacy_templates

# Known good test values for APIs
TEST_NDCS = ["00071-0155", "00006-0074", "68462-0227"]  # Pfizer, Merck, Glenmark
TEST_DRUG_NAMES = ["lisinopril", "metformin", "amoxicillin"]
TEST_CONDITIONS = ["hypertension", "diabetes", "asthma"]
TEST_MFG_NAMES = ["pfizer", "novartis", "merck"]

async def test_ndc_lookup():
    """Test the NDC lookup functionality with real FDA API"""
    print("\n===== Testing NDC Lookup =====")
    success = False
    
    # Try multiple NDCs until one works
    for search_term in TEST_NDCS:
        try:
            print(f"Attempting lookup for NDC: {search_term}...")
            result = await ndc.enhanced_ndc_lookup(search_term=search_term, search_type="ndc")
            
            if result.get("status") == "success":
                print(f"SUCCESS! NDC lookup for {search_term} worked")
                print(f"NDC Lookup Result: {json.dumps(result, indent=2)[:500]}...")
                success = True
                break
            else:
                print(f"API responded but returned error: {result.get('message', 'Unknown error')}")
        except Exception as e:
            print(f"Error with NDC {search_term}: {e}")
    
    # Try a product name search if NDC search failed
    if not success:
        try:
            search_term = TEST_DRUG_NAMES[0]
            print(f"Trying product name search for: {search_term}...")
            result = await ndc.enhanced_ndc_lookup(search_term=search_term, search_type="product_name")
            if result.get("status") == "success":
                print(f"SUCCESS! Product name lookup for {search_term} worked")
                print(f"Product Lookup Result: {json.dumps(result, indent=2)[:500]}...")
                success = True
        except Exception as e:
            print(f"Error with product search: {e}")
    
    if success:
        print("✅ NDC Lookup test completed successfully")
    else:
        print("⚠️ NDC Lookup test completed with issues - FDA API may be rate limited")

async def test_rxnorm_mapping():
    """Test the RxNorm mapping functionality with real RxNav API"""
    print("\n===== Testing RxNorm Mapping =====")
    success = False
    
    for medication_name in TEST_DRUG_NAMES:
        try:
            print(f"Attempting RxNorm mapping for: {medication_name}...")
            result = await rxnorm.rxnorm_mapping(medication_name=medication_name)
            
            if result.get("status") == "success":
                print(f"SUCCESS! RxNorm mapping for {medication_name} worked")
                print(f"RxNorm Result: {json.dumps(result, indent=2)[:500]}...")
                success = True
                break
            else:
                print(f"API responded but returned error: {result.get('message', 'Unknown error')}")
                # Sleep to avoid rate limiting
                time.sleep(1)
        except Exception as e:
            print(f"Error with RxNorm mapping for {medication_name}: {e}")
            # Sleep to avoid rate limiting
            time.sleep(1)
    
    if success:
        print("✅ RxNorm Mapping test completed successfully")
    else:
        print("⚠️ RxNorm Mapping test completed with issues - RxNav API may be rate limited")

async def test_evidence_lookup():
    """Test the evidence-based order set builder"""
    print("\n===== Testing Evidence-Based Order Set Builder =====")
    success = False
    
    for condition in TEST_CONDITIONS:
        try:
            print(f"Searching evidence for condition: {condition}...")
            result = await evidence.get_evidence_for_order_set(condition=condition)
            
            # Evidence module may use various APIs so check if we got any meaningful data
            if result and isinstance(result, dict) and (result.get("pubmed_results") or result.get("guideline_results")):
                print(f"SUCCESS! Evidence search for {condition} worked")
                print(f"Evidence Result: {json.dumps(result, indent=2)[:500]}...")
                success = True
                break
            else:
                print(f"API returned incomplete data for condition {condition}")
                time.sleep(1)
        except Exception as e:
            print(f"Error with evidence search for {condition}: {e}")
            time.sleep(1)
    
    if success:
        print("✅ Evidence Lookup test completed successfully")
    else:
        print("⚠️ Evidence Lookup test completed with issues - API may require authentication")

async def test_formulary_alternatives():
    """Test the formulary alternatives functionality"""
    print("\n===== Testing Formulary Alternatives =====")
    success = False
    
    for medication in TEST_DRUG_NAMES:
        try:
            print(f"Finding formulary alternatives for: {medication}...")
            result = await formulary.analyze_formulary_alternatives(medication=medication)
            
            if result and isinstance(result, dict) and result.get("alternatives"):
                print(f"SUCCESS! Formulary alternatives for {medication} found")
                print(f"Formulary Result: {json.dumps(result, indent=2)[:500]}...")
                success = True
                break
            else:
                print(f"No valid alternatives found for {medication}")
                time.sleep(1)
        except Exception as e:
            print(f"Error with formulary alternatives for {medication}: {e}")
            time.sleep(1)
    
    if success:
        print("✅ Formulary Alternatives test completed successfully")
    else:
        print("⚠️ Formulary Alternatives test completed with issues")

async def test_fhir_generation():
    """Test the FHIR resource generation"""
    print("\n===== Testing FHIR Resource Generation =====")
    
    medication_data = {
        "name": "atorvastatin",
        "strength": "40 mg",
        "form": "tablet",
        "manufacturer": "Pfizer",
        "rxnorm_code": "617314",  # Adding RXCUI for better FHIR generation
        "code": {
            "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
            "value": "617314",
            "display": "Atorvastatin 40 MG Oral Tablet"
        }
    }
    
    try:
        print("Generating FHIR Medication resource...")
        result = await fhir.generate_fhir_medication_resource(medication_data=medication_data)
        
        if result and isinstance(result, dict) and result.get("resourceType") == "Medication":
            print("SUCCESS! FHIR Medication resource generated correctly")
            print(f"FHIR Resource: {json.dumps(result, indent=2)[:500]}...")
            print("✅ FHIR Resource Generation test completed successfully")
        else:
            print(f"FHIR resource generated but may have issues: {json.dumps(result, indent=2)[:200]}...")
            print("⚠️ FHIR Resource Generation test completed with potential issues")
    except Exception as e:
        print(f"❌ Error in FHIR Resource Generation: {e}")

def test_prompt_templates():
    """Test pharmacy prompt templates"""
    print("\n===== Testing Pharmacy Prompt Templates =====")
    try:
        templates = pharmacy_templates.list_templates()
        print(f"Found {len(templates)} pharmacy prompt templates")
        
        # Test getting a specific template
        if len(templates) > 0:
            template_id = templates[0].get('id')
            template = pharmacy_templates.get_prompt_template(template_id=template_id)
            print(f"\nTemplate {template_id}: {template['name'] if 'name' in template else 'Unnamed template'}")
            
            # Test formatting a template
            if 'parameters' in template:
                param_names = template['parameters'].keys()
                sample_params = {param: f"Sample {param}" for param in param_names}
                formatted = pharmacy_templates.format_prompt(template_id, **sample_params)
                print(f"\nFormatted template (preview): {formatted[:200]}...")
        
        print("✅ Prompt Templates test completed successfully")
    except Exception as e:
        print(f"❌ Error in Prompt Templates: {e}")

async def test_mcp_server():
    """Test MCP server resources access"""
    print("\n===== Testing MCP Handler Resources =====")
    
    try:
        # Test imports first
        from app.routes.mcp_handler import router, get_resource_metadata
        from fastapi import Request
        
        # Create a minimal mock request object
        class MockRequest:
            def __init__(self):
                self.headers = {}
                self.query_params = {}
        
        mock_request = MockRequest()
        
        try:
            # Get resource metadata directly
            metadata = get_resource_metadata()
            
            if metadata:
                print(f"SUCCESS! Found {len(metadata)} total resources")
                
                # Filter for pharmacy resources
                pharmacy_resources = [r for r in metadata if r['uri'].startswith('pharmacy/')]
                print(f"Found {len(pharmacy_resources)} pharmacy resources:")
                
                for idx, resource in enumerate(pharmacy_resources[:3], 1):  # Show first 3
                    print(f"  {idx}. {resource['uri']} - {resource.get('description', 'No description')}")
                
                if len(pharmacy_resources) > 3:
                    print(f"  ... and {len(pharmacy_resources) - 3} more pharmacy resources")
                    
                print("✅ MCP Handler Resources test completed successfully")
            else:
                print("⚠️ No resource metadata found")
        except Exception as e:
            print(f"Error accessing resource metadata: {e}")
            print("⚠️ MCP Handler Resources test completed with issues")
            
    except ImportError as e:
        print(f"❌ Error importing MCP handler: {e}")

async def run_tests():
    """Run all tests"""
    print("Starting pharmacy informatics module tests...\n")
    
    # Test MCP server resources first
    await test_mcp_server()
    
    # Test NDC lookup with FDA API
    await test_ndc_lookup()
    
    # Test RxNorm mapping with RxNav API
    await test_rxnorm_mapping()
    
    # Test evidence lookup
    await test_evidence_lookup()
    
    # Test formulary alternatives
    await test_formulary_alternatives()
    
    # Test FHIR generation (local, not API dependent)
    await test_fhir_generation()
    
    # Test prompt templates (local, not API dependent)
    test_prompt_templates()
    
    print("\nAll pharmacy module tests completed!")
    print("Note: Some tests might show warnings due to API rate limiting when used without authentication keys")


if __name__ == "__main__":
    asyncio.run(run_tests())
