#!/usr/bin/env python3
"""
Direct FDA Drug Search with Clean Display
A simplified implementation showing FDA drug data in a clear format.
"""
import requests
import pandas as pd
import sys
from rich.console import Console

console = Console(width=120)  # Set wider console to prevent wrapping

def get_fda_drug_data(query):
    """Query the FDA API directly for drug data"""
    console.print(f"[bold blue]Searching for drug: [/bold blue][bold green]{query}[/bold green]")
    
    # FDA API URL with properly formatted search
    url = f"https://api.fda.gov/drug/ndc.json?search=(brand_name:{query}+generic_name:{query})&limit=10"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if "results" in data:
            total = data.get("meta", {}).get("results", {}).get("total", 0)
            console.print(f"[bold green]Found {total} results for {query}[/bold green]")
            return data["results"]
        else:
            console.print("[bold red]No results found[/bold red]")
            return []
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")
        return []

def process_results(results):
    """Process FDA results into a clean dataframe"""
    processed_data = []
    
    for item in results:
        # Extract active ingredients
        active_ingredients = item.get("active_ingredients", [])
        strength = active_ingredients[0].get("strength", "") if active_ingredients else ""
        
        # Extract manufacturer name (matching your PillQ app's format)
        manufacturer = "Unknown"
        if "openfda" in item and "manufacturer_name" in item["openfda"]:
            manufacturer = item["openfda"]["manufacturer_name"][0]
        
        # Create entry with the same fields as your PillQ app
        entry = {
            "NDC": item.get("product_ndc", ""),
            "brand_name": item.get("brand_name", ""),
            "generic_name": item.get("generic_name", ""),
            "strength": strength,
            "route": item.get("route", [""])[0] if isinstance(item.get("route"), list) else item.get("route", ""),
            "dosage_form": item.get("dosage_form", ""),
            "manufacturer": manufacturer
        }
        processed_data.append(entry)
    
    return processed_data

def display_as_table(data):
    """Display the data in a clean pandas DataFrame"""
    if not data:
        console.print("[bold red]No data to display[/bold red]")
        return
    
    # Create DataFrame for clean display
    df = pd.DataFrame(data)
    
    # Print header
    console.print("\n[bold blue]========== FDA Drug Search Results ==========[/bold blue]\n")
    
    # Format and print the dataframe with clean index
    df.index = range(len(df))  # Start index at 0
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 120)
    pd.set_option('display.colheader_justify', 'left')
    
    console.print(df.to_string())
    console.print(f"\n[bold green]Total results displayed: {len(data)}[/bold green]")

if __name__ == "__main__":
    # Get search term from command line or use default
    query = "apixaban"
    if len(sys.argv) > 1:
        query = sys.argv[1]
    
    # Get FDA data
    results = get_fda_drug_data(query)
    
    # Process and display results
    processed_data = process_results(results)
    display_as_table(processed_data)
