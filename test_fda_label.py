#!/usr/bin/env python3
"""
Test script for the FDA Label Data retrieval endpoint
Tests both direct endpoint access and access via the MCP protocol
"""
import requests
import json
import asyncio
from rich.console import Console

# Configure console for pretty output
console = Console(width=120)

# Server URL (modify if needed)
BASE_URL = "http://localhost:8000"

def test_direct_label_endpoint(drug_name, fields=None):
    """Test the direct FDA label endpoint"""
    console.print(f"[bold blue]Testing direct FDA label endpoint for drug: [/bold blue][bold green]{drug_name}[/bold green]")
    
    url = f"{BASE_URL}/fda/label/search"
    params = {"name": drug_name}
    
    if fields:
        params["fields"] = fields
    
    console.print(f"[dim]URL: {url}[/dim]")
    console.print(f"[dim]Params: {params}[/dim]")
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        result = response.json()
        
        console.print("[bold green]✓ Successfully retrieved label data[/bold green]")
        
        # Display the results
        console.print("\n[bold blue]Label Data Result:[/bold blue]")
        console.print(f"Drug Name: {result['drug_name']}")
        console.print(f"Fields Retrieved: {len(result['fields'])}")
        
        # Display each field
        for field in result['fields']:
            console.print(f"\n[bold cyan]{field['field_name'].upper()}[/bold cyan]")
            # Show truncated values
            for value in field['values']:
                console.print(f"  {value[:200]}..." if len(value) > 200 else f"  {value}")
        
        return result
        
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        return None

def test_mcp_label_endpoint(drug_name, fields=None):
    """Test accessing the FDA label data via the MCP protocol"""
    console.print(f"[bold blue]Testing MCP FDA label endpoint for drug: [/bold blue][bold green]{drug_name}[/bold green]")
    
    url = f"{BASE_URL}/resources/fda/label/data/execute"
    
    # Build arguments for the MCP call
    arguments = {"name": drug_name}
    if fields:
        arguments["fields"] = fields
        
    payload = {"arguments": arguments}
    
    console.print(f"[dim]URL: {url}[/dim]")
    console.print(f"[dim]Payload: {payload}[/dim]")
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        console.print("[bold green]✓ Successfully retrieved label data via MCP[/bold green]")
        
        # Display the results
        console.print("\n[bold blue]MCP Label Data Result:[/bold blue]")
        if "result" in result:
            drug_data = result["result"]
            console.print(f"Drug Name: {drug_data['drug_name']}")
            console.print(f"Fields Retrieved: {len(drug_data['fields'])}")
            
            # Display a sample of fields
            sample_size = min(3, len(drug_data['fields']))
            console.print(f"\n[bold yellow]Sample of {sample_size} fields:[/bold yellow]")
            
            for i in range(sample_size):
                field = drug_data['fields'][i]
                console.print(f"\n[bold cyan]{field['field_name'].upper()}[/bold cyan]")
                # Show truncated values for first field only
                for value in field['values'][:1]:  # Just show first value in each field
                    console.print(f"  {value[:150]}..." if len(value) > 150 else f"  {value}")
        
        return result
        
    except Exception as e:
        console.print(f"[bold red]Error with MCP endpoint: {str(e)}[/bold red]")
        if hasattr(e, 'response') and e.response:
            console.print(f"[bold red]Response: {e.response.text}[/bold red]")
        return None

if __name__ == "__main__":
    drugs_to_test = ["apixaban", "ceftriaxone"]
    fields_to_request = "active_ingredient,inactive_ingredient,indications_and_usage,warnings"
    
    for drug in drugs_to_test:
        console.print(f"\n[bold]{'='*50}[/bold]")
        console.print(f"[bold]Testing label data for drug: {drug}[/bold]")
        console.print(f"[bold]{'='*50}[/bold]\n")
        
        # Test direct endpoint
        test_direct_label_endpoint(drug, fields_to_request)
        
        # Test MCP endpoint 
        test_mcp_label_endpoint(drug, fields_to_request)
