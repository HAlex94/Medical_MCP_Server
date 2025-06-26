#!/usr/bin/env python3
"""
FDA Label Data Extraction Test
Tests retrieving specific label data fields for an NDC
"""
import requests
import json
from rich.console import Console

console = Console(width=120)

def get_ndc_label_data(ndc):
    """Get detailed label data for a specific NDC"""
    # Clean NDC format (remove dashes if present)
    clean_ndc = ndc.replace("-", "")
    
    # FDA API endpoint for drug label information
    url = f"https://api.fda.gov/drug/label.json?search=openfda.product_ndc:{clean_ndc}"
    
    console.print(f"[bold blue]Querying FDA Label API for NDC: [/bold blue][bold green]{ndc}[/bold green]")
    console.print(f"[dim]URL: {url}[/dim]")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Check if we have results
        if "results" in data and len(data["results"]) > 0:
            console.print(f"[bold green]✓ Found label data for NDC {ndc}[/bold green]")
            
            # Get the first result (should be only one for a specific NDC)
            label_data = data["results"][0]
            
            # Output available fields in the label data
            console.print("[bold blue]Available label data fields:[/bold blue]")
            for key in label_data.keys():
                console.print(f"  - [cyan]{key}[/cyan]")
            
            # Extract specific fields shown in the PillQ app screenshot
            fields_to_extract = {
                "active_ingredient": label_data.get("active_ingredient", ["Not Available"]),
                "inactive_ingredient": label_data.get("inactive_ingredient", ["Not Available"]),
                "indications_and_usage": label_data.get("indications_and_usage", ["Not Available"])
            }
            
            # Print the extracted fields
            console.print("\n[bold blue]Extracted Fields:[/bold blue]")
            console.print(json.dumps(fields_to_extract, indent=2))
            
            return fields_to_extract
        else:
            console.print(f"[bold red]No label data found for NDC {ndc}[/bold red]")
            return None
            
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        return None

if __name__ == "__main__":
    # Test with the NDC from the screenshot
    ndc = "0409-7335-20"
    get_ndc_label_data(ndc)
