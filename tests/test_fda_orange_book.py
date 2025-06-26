#!/usr/bin/env python3
"""
FDA Orange Book API Tests

This file contains tests for the FDA Orange Book API integration,
including direct API tests and endpoint tests for the FastAPI server.
"""
import asyncio
import httpx
import json
import os
import pytest
import sys
import time
import traceback
from datetime import datetime

# Test drugs with proven therapeutic equivalence data
TEST_DRUGS = [
    {"name": "Lipitor", "active": "atorvastatin", "ndc": "0071-0156", "category": "Statin"},
    {"name": "Prozac", "active": "fluoxetine", "ndc": "0777-3105", "category": "SSRI"},
    {"name": "Norvasc", "active": "amlodipine", "ndc": "0069-1530", "category": "Calcium Channel Blocker"},
    {"name": "Zoloft", "active": "sertraline", "ndc": "0049-4900", "category": "SSRI"}
]

# Local server settings for endpoint tests
SERVER_URL = "http://localhost:8000"
API_BASE_PATH = "/api/v1/fda"
ORANGE_BOOK_SEARCH_PATH = f"{API_BASE_PATH}/orange-book/search"
ORANGE_BOOK_EQUIVALENT_PATH = f"{API_BASE_PATH}/orange-book/equivalent-products"

async def test_server_connection():
    """Check if the server is running and accessible"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{SERVER_URL}/docs")
            if response.status_code == 200:
                return True
            else:
                return False
    except Exception as e:
        print(f"Cannot connect to server at {SERVER_URL}: {str(e)}")
        return False

async def query_fda_api(search_query, limit=5, timeout=30.0, retry=True):
    """Query the FDA API with the given search query, with retry logic"""
    url = "https://api.fda.gov/drug/drugsfda.json"
    params = {"search": search_query, "limit": limit}
    
    for attempt in range(3):  # Retry up to 3 times
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 500 and retry and attempt < 2:
                # Server error, wait and retry
                wait_time = 2 * (attempt + 1)  # Exponential backoff
                print(f"Server error, waiting {wait_time}s before retry {attempt+1}")
                time.sleep(wait_time)
            else:
                # Propagate the error if final retry or not 500 error
                raise
        except httpx.RequestError as e:
            # Connection error, wait and retry
            if retry and attempt < 2:
                wait_time = 2 * (attempt + 1)
                print(f"Connection error, waiting {wait_time}s before retry {attempt+1}")
                time.sleep(wait_time)
            else:
                raise

    raise Exception("Failed after multiple retries")

async def test_drug_te_codes(drug_info):
    """Test therapeutic equivalence codes for a specific drug via direct FDA API access"""
    results = {
        "brand_search": False,
        "active_search": False,
        "te_codes": set(),
        "reference_drug": False,
        "generics_found": 0,
        "error": None
    }
    
    try:
        # 1. Test search by brand name
        possible_brand_queries = [
            f"openfda.brand_name:\"{drug_info['name']}\"",  # Primary field path
            f"brand_name:\"{drug_info['name']}\"",         # Alternative path
            f"trade_name:\"{drug_info['name']}\""          # Alternative path
        ]
        
        brand_result = None
        for query in possible_brand_queries:
            try:
                brand_result = await query_fda_api(query, retry=True)
                if brand_result and brand_result.get('results'):
                    results["brand_search"] = True
                    break
            except Exception:
                continue
                
        if results["brand_search"]:
            # Extract product info and TE codes
            for product_data in brand_result.get('results', []):
                if 'products' in product_data:
                    for product in product_data['products']:
                        # Get TE code
                        te_code = product.get('te_code')
                        
                        if te_code:
                            results["te_codes"].add(te_code)
                            
                        # Check if it's a reference drug
                        if product.get('reference_drug') == 'Yes':
                            results["reference_drug"] = True
            
        # 2. Test search by active ingredient for generics
        possible_active_queries = [
            f"openfda.generic_name:\"{drug_info['active']}\"",  # Primary field path
            f"active_ingredient:\"{drug_info['active']}\"",     # Alternative path
            f"openfda.substance_name:\"{drug_info['active']}\""  # Alternative path
        ]
        
        active_result = None
        for query in possible_active_queries:
            try:
                active_result = await query_fda_api(query, limit=10, retry=True)
                if active_result and active_result.get('results'):
                    results["active_search"] = True
                    break
            except Exception:
                continue
        
        if results["active_search"]:
            generic_products = []
            
            # Extract product info from active ingredient search
            for product_data in active_result.get('results', []):
                if 'products' in product_data:
                    for product in product_data['products']:
                        # Get brand/generic name
                        product_name = product.get('brand_name') or 'Generic'
                        
                        # Skip if this is the brand product we already found
                        if product_name.upper() == drug_info['name'].upper():
                            continue
                            
                        # Get TE code
                        te_code = product.get('te_code')
                        
                        if te_code:
                            results["te_codes"].add(te_code)
                            
                        generic_products.append({
                            'name': product_name,
                            'te_code': te_code
                        })
            
            results["generics_found"] = len(generic_products)
            
    except Exception as e:
        results["error"] = str(e)
    
    return results

async def test_orange_book_search_endpoint(drug_name=None, active_ingredient=None, ndc=None):
    """Test the Orange Book search endpoint via local server"""
    params = {}
    
    if drug_name:
        params["name"] = drug_name
    
    if active_ingredient:
        params["active_ingredient"] = active_ingredient
        
    if ndc:
        params["ndc"] = ndc
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{SERVER_URL}{ORANGE_BOOK_SEARCH_PATH}", params=params)
            response.raise_for_status()
            data = response.json()
            
            # Check for therapeutic equivalence codes in the results
            te_codes = set()
            for product in data.get("results", []):
                if product.get("te_code"):
                    te_codes.add(product.get("te_code"))
            
            return data, te_codes
                
    except Exception as e:
        print(f"Error searching Orange Book: {str(e)}")
        return None, set()

async def test_equivalent_products_endpoint(ndc):
    """Test the equivalent products endpoint via local server"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{SERVER_URL}{ORANGE_BOOK_EQUIVALENT_PATH}", params={"ndc": ndc})
            response.raise_for_status()
            data = response.json()
            
            # Check for therapeutic equivalence codes in the results
            te_codes = set()
            for product in data.get("equivalent_products", []):
                if product.get("te_code"):
                    te_codes.add(product.get("te_code"))
            
            return data, te_codes
                
    except Exception as e:
        print(f"Error getting equivalent products: {str(e)}")
        return None, set()

@pytest.mark.asyncio
async def test_direct_fda_api_access():
    """Direct FDA API test for therapeutic equivalence codes"""
    success_count = 0
    
    for drug in TEST_DRUGS:
        results = await test_drug_te_codes(drug)
        
        # Test is successful if we found the brand, some generics, and TE codes
        if results["brand_search"] and results["generics_found"] > 0 and results["te_codes"]:
            success_count += 1
            
    # We want at least 50% of drugs to return data successfully
    assert success_count >= len(TEST_DRUGS) / 2, f"Only {success_count}/{len(TEST_DRUGS)} drugs returned therapeutic equivalence data"
    
    # Verify we got some AB ratings in our results
    all_te_codes = set()
    for drug in TEST_DRUGS:
        results = await test_drug_te_codes(drug)
        all_te_codes.update(results["te_codes"])
    
    # Ensure we found some valuable TE codes
    valuable_codes = {"AB", "AA", "AB1", "AB2"}
    found_valuable_codes = valuable_codes.intersection(all_te_codes)
    assert found_valuable_codes, f"No valuable TE codes found among {all_te_codes}"

# For manual testing
async def run_manual_tests():
    """Run tests for the FDA Orange Book API integration manually"""
    print("\n🧪 FDA ORANGE BOOK API TESTS 🧪")
    
    # Check if server is running for endpoint tests
    server_up = await test_server_connection()
    
    # Test direct FDA API
    print("\n🔍 TESTING DIRECT FDA API ACCESS")
    success_count = 0
    for drug in TEST_DRUGS:
        print(f"\n💊 Testing: {drug['name']} ({drug['category']})")
        results = await test_drug_te_codes(drug)
        
        print(f"✓ Brand found: {results['brand_search']}")
        print(f"✓ Generics found: {results['generics_found']}")
        print(f"✓ TE Codes: {', '.join(results['te_codes']) if results['te_codes'] else 'None'}")
        print(f"✓ Reference Drug: {results['reference_drug']}")
        
        # Test is successful if we found the brand, some generics, and TE codes
        if results["brand_search"] and results["generics_found"] > 0 and results["te_codes"]:
            success_count += 1
            print(f"✅ {drug['name']} test SUCCESS")
        else:
            print(f"❌ {drug['name']} test FAILED")
    
    print(f"\n📊 Direct API test success: {success_count}/{len(TEST_DRUGS)} drugs ({success_count/len(TEST_DRUGS)*100:.1f}%)")
    
    # Optional server endpoint tests if server is running
    if server_up:
        print("\n🔍 TESTING SERVER ENDPOINTS")
        endpoint_success = 0
        
        for drug in TEST_DRUGS[:2]:  # Test just the first two drugs
            # Test search endpoint with name
            data, te_codes = await test_orange_book_search_endpoint(drug_name=drug["name"])
            if data and te_codes:
                endpoint_success += 1
                print(f"✅ Search by name for {drug['name']} SUCCESS")
                print(f"   Found TE codes: {', '.join(te_codes)}")
            else:
                print(f"❌ Search by name for {drug['name']} FAILED")
                
            # Test equivalent products endpoint
            data, te_codes = await test_equivalent_products_endpoint(drug["ndc"])
            if data and data.get("equivalent_products") and te_codes:
                endpoint_success += 1
                print(f"✅ Equivalent products for {drug['name']} SUCCESS")
                print(f"   Found TE codes: {', '.join(te_codes)}")
            else:
                print(f"❌ Equivalent products for {drug['name']} FAILED")
                
        print(f"\n📊 Server endpoint tests completed with {endpoint_success}/4 successes")
    else:
        print("\n⚠️ Server is not running. Skipping endpoint tests.")
        print("Start your server with: uvicorn app.main:app --reload")
    
    print("\n🧪 FDA ORANGE BOOK API TESTS COMPLETE 🧪")

if __name__ == "__main__":
    asyncio.run(run_manual_tests())
