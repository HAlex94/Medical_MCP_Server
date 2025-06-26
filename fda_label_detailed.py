#!/usr/bin/env python3
"""
Comprehensive FDA Label Data Test
First finds drugs by name/ingredient, then fetches detailed label information for a selected NDC
"""
import requests
import json
from rich.console import Console
from rich.table import Table
import sys

console = Console(width=120)

def find_drug_products(query):
    """First find drug products matching the query"""
    url = f"https://api.fda.gov/drug/ndc.json?search=(brand_name:{query}+generic_name:{query})&limit=5"
    
    console.print(f"[bold blue]Step 1: Finding drugs matching: [/bold blue][bold green]{query}[/bold green]")
    console.print(f"[dim]URL: {url}[/dim]")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if "results" in data:
            products = data["results"]
            console.print(f"[bold green]✓ Found {len(products)} products[/bold green]")
            
            # Display products in a table
            table = Table(title=f"Products matching '{query}'")
            table.add_column("Index", style="dim")
            table.add_column("NDC", style="cyan")
            table.add_column("Brand Name", style="green")
            table.add_column("Generic Name", style="blue")
            table.add_column("Manufacturer", style="magenta")
            
            for i, product in enumerate(products):
                # Extract manufacturer name
                manufacturer = "Unknown"
                if "openfda" in product and "manufacturer_name" in product["openfda"]:
                    manufacturer = product["openfda"]["manufacturer_name"][0]
                    
                table.add_row(
                    str(i),
                    product.get("product_ndc", ""),
                    product.get("brand_name", ""),
                    product.get("generic_name", ""),
                    manufacturer
                )
            
            console.print(table)
            return products
        else:
            console.print(f"[bold red]No products found matching '{query}'[/bold red]")
            return []
            
    except Exception as e:
        console.print(f"[bold red]Error finding products: {str(e)}[/bold red]")
        return []

def get_detailed_label_data(product):
    """Get detailed label data using both product_ndc and spl_id approaches"""
    ndc = product.get("product_ndc", "")
    
    # First try using the SPL ID if available (more reliable)
    spl_id = None
    if "openfda" in product and "spl_id" in product["openfda"]:
        spl_id = product["openfda"]["spl_id"][0]
        
    # Try querying by SPL ID first (usually more reliable than NDC for labels)
    if spl_id:
        console.print(f"[bold blue]Trying to get label data using SPL ID: [/bold blue][bold green]{spl_id}[/bold green]")
        
        # FDA API endpoint for label data using SPL ID
        spl_url = f"https://api.fda.gov/drug/label.json?search=openfda.spl_id:{spl_id}"
        
        try:
            response = requests.get(spl_url)
            if response.status_code == 200:
                data = response.json()
                if "results" in data and len(data["results"]) > 0:
                    console.print(f"[bold green]✓ Found label data using SPL ID[/bold green]")
                    return data["results"][0]
        except Exception:
            pass
    
    # If SPL ID approach failed, try using NDC
    console.print(f"[bold blue]Trying to get label data using NDC: [/bold blue][bold green]{ndc}[/bold green]")
    
    # FDA API endpoint for label data using NDC
    clean_ndc = ndc.replace("-", "")
    url = f"https://api.fda.gov/drug/label.json?search=openfda.product_ndc:{clean_ndc}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if "results" in data and len(data["results"]) > 0:
            console.print(f"[bold green]✓ Found label data using NDC[/bold green]")
            return data["results"][0]
        else:
            console.print(f"[bold yellow]! No label data found for NDC {ndc}[/bold yellow]")
            return None
            
    except Exception as e:
        console.print(f"[bold red]Error getting label data: {str(e)}[/bold red]")
        
        # If we get here, try one more approach - using package NDC from openfda section
        if "openfda" in product and "package_ndc" in product["openfda"]:
            package_ndc = product["openfda"]["package_ndc"][0].replace("-", "")
            console.print(f"[bold blue]Trying alternative package NDC: [/bold blue][bold green]{package_ndc}[/bold green]")
            
            alt_url = f"https://api.fda.gov/drug/label.json?search=openfda.package_ndc:{package_ndc}"
            try:
                response = requests.get(alt_url)
                response.raise_for_status()
                data = response.json()
                
                if "results" in data and len(data["results"]) > 0:
                    console.print(f"[bold green]✓ Found label data using package NDC[/bold green]")
                    return data["results"][0]
            except Exception:
                pass
                
        return None

def display_label_fields(label_data):
    """Display the available label fields and extract specific ones"""
    console.print("\n[bold blue]Available label data fields:[/bold blue]")
    
    available_fields = []
    for key in label_data.keys():
        if key != "openfda":  # Skip the openfda nested object for clarity
            available_fields.append(key)
    
    # Display fields in columns
    columns = 3
    rows = (len(available_fields) + columns - 1) // columns
    
    table = Table(title="Available Label Data Fields")
    for i in range(columns):
        table.add_column(f"Fields {i+1}", style="cyan")
    
    for r in range(rows):
        row_data = []
        for c in range(columns):
            idx = r + c * rows
            if idx < len(available_fields):
                row_data.append(available_fields[idx])
            else:
                row_data.append("")
        table.add_row(*row_data)
    
    console.print(table)
    
    # Extract and display specific fields shown in the PillQ app screenshot
    fields_to_extract = {
        "active_ingredient": label_data.get("active_ingredient", ["Not Available"]),
        "inactive_ingredient": label_data.get("inactive_ingredient", ["Not Available"]),
        "indications_and_usage": label_data.get("indications_and_usage", ["Not Available"]),
        "dosage_and_administration": label_data.get("dosage_and_administration", ["Not Available"]),
        "warnings": label_data.get("warnings", ["Not Available"])
    }
    
    # Print the extracted fields in a clean format
    console.print("\n[bold blue]Extracted Label Fields:[/bold blue]")
    for field, values in fields_to_extract.items():
        console.print(f"[bold cyan]{field.upper()}[/bold cyan]")
        for value in values:
            console.print(f"  {value}")
        console.print("")
    
    return fields_to_extract

if __name__ == "__main__":
    # Get drug name from command line or use default
    query = "apixaban"
    if len(sys.argv) > 1:
        query = sys.argv[1]
    
    # Step 1: Find products
    products = find_drug_products(query)
    
    if products:
        # Step 2: Get label data for the first product
        product = products[0]
        console.print(f"\n[bold blue]Step 2: Fetching label data for NDC: [/bold blue][bold green]{product.get('product_ndc', '')}[/bold green]")
        
        label_data = get_detailed_label_data(product)
        
        if label_data:
            # Step 3: Display label data fields
            display_label_fields(label_data)
        else:
            console.print("[bold red]Failed to retrieve label data for this product[/bold red]")
