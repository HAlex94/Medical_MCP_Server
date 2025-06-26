#!/usr/bin/env python3
"""
Direct FDA Drug Search Test
A standalone script that directly queries the FDA API to demonstrate 
the core functionality without server/API complexity.
"""
import requests
import json
import pandas as pd
from tabulate import tabulate
import sys
from rich.console import Console
from rich.table import Table

console = Console()

def search_fda_drugs(query, limit=10):
    """
    Direct implementation of FDA drug search - simplified version of what PillQ does
    """
    # FDA API endpoint with correctly formatted search query
    url = f"https://api.fda.gov/drug/ndc.json?search=(brand_name:{query}+generic_name:{query})&limit={limit}"
    
    try:
        console.print(f"[blue]Querying FDA API for: [bold]{query}[/bold][/blue]")
        console.print(f"[dim]URL: {url}[/dim]")
        
        # Make request directly without async complexity
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        
        # Process results
        results = []
        if "results" in data:
            total = data.get("meta", {}).get("results", {}).get("total", 0)
            console.print(f"[green]✓ Found {total} results for '{query}'[/green]")
            
            # Process each product into a format matching the screenshot
            for product in data["results"]:
                # Extract active ingredient strength
                strength = ""
                if product.get("active_ingredients"):
                    strength = product.get("active_ingredients")[0].get("strength", "")
                
                # Extract manufacturer name
                manufacturer = (
                    product.get("openfda", {}).get("manufacturer_name", ["Unknown"])[0]
                    if product.get("openfda")
                    else "Unknown"
                )
                
                # Format result to match the fields shown in your screenshot
                result = {
                    "ndc": product.get("product_ndc", ""),
                    "brand_name": product.get("brand_name", ""),
                    "generic_name": product.get("generic_name", ""),
                    "strength": strength,
                    "route": product.get("route", ""),
                    "dosage_form": product.get("dosage_form", ""),
                    "manufacturer": manufacturer
                }
                results.append(result)
            
            return results
        else:
            console.print("[red]No results found in FDA API response[/red]")
            return []
            
    except requests.exceptions.HTTPError as e:
        console.print(f"[red]HTTP error: {e}[/red]")
        return []
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Error during request: {e}[/red]")
        return []
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        return []

def display_results_table(results):
    """Display results in a rich table format similar to the PillQ screenshot"""
    if not results:
        console.print("[yellow]No results to display[/yellow]")
        return
    
    # Create table matching screenshot columns
    table = Table(title="FDA Drug Search Results")
    table.add_column("#", style="dim")
    table.add_column("NDC", style="cyan")
    table.add_column("brand_name", style="green")
    table.add_column("generic_name", style="blue")
    table.add_column("strength", style="magenta")
    table.add_column("route", style="yellow")
    table.add_column("dosage_form", style="cyan")
    table.add_column("manufacturer", style="green")
    
    # Add rows
    for i, result in enumerate(results):
        table.add_row(
            str(i),
            result["ndc"],
            result["brand_name"],
            result["generic_name"],
            result["strength"],
            f"[{result['route']}]" if result["route"] else "",  # Match bracket format in screenshot
            result["dosage_form"],
            result["manufacturer"]
        )
    
    console.print(table)

if __name__ == "__main__":
    # Default query
    query = "apixaban"
    
    # Allow command-line argument for query
    if len(sys.argv) > 1:
        query = sys.argv[1]
    
    # Get and display results
    results = search_fda_drugs(query)
    display_results_table(results)
