#!/usr/bin/env python3
"""
Diagnostic script for Medical MCP Server FDA drug search endpoint.
This script will check all critical components of the API integration.
"""
import json
import requests
import os
import time
import logging
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Setup Rich console for better output
console = Console()

# URL configurations
LOCAL_URL = "http://127.0.0.1:8000"  # For local testing
RENDER_URL = "https://medical-mcp-server.onrender.com"  # For production testing
ACTIVE_URL = RENDER_URL  # Change this to test different environments

def print_separator():
    console.print("=" * 80, style="yellow")

def test_health_endpoint():
    """Test the health endpoint to confirm API is running"""
    console.print(Panel("Testing Health Endpoint", style="bold green"))
    try:
        response = requests.get(f"{ACTIVE_URL}/health")
        status_code = response.status_code
        if status_code == 200:
            console.print(f"[green]✓ Health endpoint is UP (Status: {status_code})[/green]")
            console.print(f"Response: {json.dumps(response.json(), indent=2)}")
        else:
            console.print(f"[red]✗ Health endpoint returned status {status_code}[/red]")
            console.print(f"Response: {response.text}")
        return status_code == 200
    except Exception as e:
        console.print(f"[red]✗ Error calling health endpoint: {str(e)}[/red]")
        return False

def test_mcp_resources_list():
    """Test the MCP resources list endpoint to verify API resources are registered"""
    console.print(Panel("Testing MCP Resources List Endpoint", style="bold green"))
    try:
        response = requests.post(
            f"{ACTIVE_URL}/resources/list", 
            json={"cursor": ""}
        )
        if response.status_code == 200:
            console.print(f"[green]✓ Resources list endpoint is working (Status: {response.status_code})[/green]")
            
            # Check if our specific resource exists
            data = response.json()
            found_resource = False
            resource_details = None
            
            # Pretty print resources list
            table = Table(title="Available MCP Resources")
            table.add_column("URI", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Description", style="blue")
            
            if "resources" in data:
                for resource in data["resources"]:
                    table.add_row(
                        resource.get("uri", "N/A"),
                        resource.get("name", "N/A"),
                        resource.get("description", "N/A")[:50] + "..." if resource.get("description") else "N/A"
                    )
                    
                    if resource.get("uri") == "fda/drug/search":
                        found_resource = True
                        resource_details = resource
            
            console.print(table)
            
            if found_resource:
                console.print(f"[green]✓ 'fda/drug/search' resource found[/green]")
                console.print(f"Resource Details: {json.dumps(resource_details, indent=2)}")
            else:
                console.print(f"[red]✗ 'fda/drug/search' resource NOT found in resources list[/red]")
            
            return found_resource
        else:
            console.print(f"[red]✗ Resources list endpoint returned status {response.status_code}[/red]")
            console.print(f"Response: {response.text}")
            return False
    except Exception as e:
        console.print(f"[red]✗ Error calling resources list endpoint: {str(e)}[/red]")
        return False

def test_direct_fda_endpoint(drug_name="apixaban", limit=3):
    """Test the direct FDA endpoint"""
    console.print(Panel(f"Testing Direct FDA Endpoint for '{drug_name}'", style="bold green"))
    try:
        response = requests.get(
            f"{ACTIVE_URL}/fda/ndc/compact_search",
            params={"name": drug_name, "limit": limit}
        )
        console.print(f"Request URL: {response.request.url}")
        
        if response.status_code == 200:
            console.print(f"[green]✓ Direct FDA endpoint is working (Status: {response.status_code})[/green]")
            data = response.json()
            
            total_results = data.get("total_results", 0)
            displayed_results = data.get("displayed_results", 0)
            products = data.get("products", [])
            
            console.print(f"Total Results: {total_results}")
            console.print(f"Displayed Results: {displayed_results}")
            
            if products:
                console.print(f"First Product Sample: {json.dumps(products[0], indent=2)}")
            else:
                console.print("[yellow]No products found in the response[/yellow]")
            
            return len(products) > 0
        else:
            console.print(f"[red]✗ Direct FDA endpoint returned status {response.status_code}[/red]")
            console.print(f"Response: {response.text}")
            return False
    except Exception as e:
        console.print(f"[red]✗ Error calling direct FDA endpoint: {str(e)}[/red]")
        return False

def test_mcp_execute_endpoint(drug_name="apixaban", limit=3):
    """Test the MCP execute endpoint with fda/drug/search resource"""
    console.print(Panel(f"Testing MCP Execute Endpoint for 'fda/drug/search' with '{drug_name}'", style="bold green"))
    try:
        response = requests.post(
            f"{ACTIVE_URL}/resources/fda/drug/search/execute",
            json={
                "arguments": {
                    "name": drug_name,
                    "limit": limit
                }
            }
        )
        console.print(f"Request URL: {response.request.url}")
        console.print(f"Request Body: {json.dumps(response.request.body.decode() if hasattr(response.request, 'body') and response.request.body else {}, indent=2)}")
        
        if response.status_code == 200:
            console.print(f"[green]✓ MCP execute endpoint is working (Status: {response.status_code})[/green]")
            data = response.json()
            console.print(f"Response: {json.dumps(data, indent=2)}")
            return True
        else:
            console.print(f"[red]✗ MCP execute endpoint returned status {response.status_code}[/red]")
            console.print(f"Response: {response.text}")
            return False
    except Exception as e:
        console.print(f"[red]✗ Error calling MCP execute endpoint: {str(e)}[/red]")
        return False

def run_all_tests():
    """Run all diagnostic tests"""
    console.print(Panel(f"Running Diagnostic Tests for {ACTIVE_URL}", style="bold blue"))
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Health Endpoint
    print_separator()
    if test_health_endpoint():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 2: MCP Resources List
    print_separator()
    if test_mcp_resources_list():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 3: Direct FDA Endpoint
    print_separator()
    if test_direct_fda_endpoint():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 4: MCP Execute Endpoint
    print_separator()
    if test_mcp_execute_endpoint():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Summary
    print_separator()
    console.print(Panel(f"Diagnostic Summary: {tests_passed} passed, {tests_failed} failed", 
                        style="green" if tests_failed == 0 else "red"))

if __name__ == "__main__":
    run_all_tests()
