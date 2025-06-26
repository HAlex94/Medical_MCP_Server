#!/usr/bin/env python3
"""
FDA Label Data by Drug Name
Demonstrates a direct search for drug label data by drug name
"""
import requests
import json
from rich.console import Console
import sys

console = Console(width=120)

def get_label_data_by_drug_name(drug_name):
    """
    Get label data directly by searching for the drug name
    in the FDA label database (matches how PillQ would access this data)
    """
    # FDA API endpoint for drug label search by drug name
    url = f"https://api.fda.gov/drug/label.json?search=openfda.generic_name:{drug_name}+openfda.brand_name:{drug_name}&limit=1"
    
    console.print(f"[bold blue]Searching FDA label database for: [/bold blue][bold green]{drug_name}[/bold green]")
    console.print(f"[dim]URL: {url}[/dim]")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if "results" in data and len(data["results"]) > 0:
            console.print(f"[bold green]✓ Found label data for {drug_name}[/bold green]")
            
            # Get the first result
            label_data = data["results"][0]
            
            # Display available label fields
            console.print("\n[bold blue]Available label data fields:[/bold blue]")
            for key in label_data.keys():
                if key != "openfda":  # Skip the openfda nested object for clarity
                    console.print(f"  - [cyan]{key}[/cyan]")
            
            # Create a structured response
            structured_data = {}
            
            # Extract specific fields of interest
            fields_of_interest = [
                "active_ingredient", 
                "inactive_ingredient",
                "indications_and_usage",
                "dosage_and_administration",
                "warnings",
                "warnings_and_cautions",
                "contraindications",
                "adverse_reactions",
                "drug_interactions"
            ]
            
            for field in fields_of_interest:
                if field in label_data:
                    structured_data[field] = label_data[field]
            
            # Print the extracted fields
            console.print("\n[bold blue]Extracted Label Fields:[/bold blue]")
            for field, values in structured_data.items():
                console.print(f"[bold cyan]{field.upper()}[/bold cyan]")
                for value in values:
                    console.print(f"  {value[:200]}..." if len(value) > 200 else f"  {value}")
                console.print("")
            
            return {
                "status": "success",
                "drug_name": drug_name,
                "label_data": structured_data
            }
        else:
            console.print(f"[bold red]No label data found for {drug_name}[/bold red]")
            return {
                "status": "error",
                "message": f"No label data found for {drug_name}"
            }
            
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        return {
            "status": "error",
            "message": f"Error retrieving label data: {str(e)}"
        }

if __name__ == "__main__":
    # Get drug name from command line or use default
    drug_name = "apixaban"
    if len(sys.argv) > 1:
        drug_name = sys.argv[1]
    
    # Get label data by drug name
    result = get_label_data_by_drug_name(drug_name)
    
    # For debugging/testing - save full response to a file
    if result["status"] == "success":
        with open(f"{drug_name}_label_data.json", "w") as f:
            json.dump(result["label_data"], f, indent=2)
        console.print(f"[bold green]✓ Saved complete label data to {drug_name}_label_data.json[/bold green]")
