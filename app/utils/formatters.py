"""
Data Format Converters

Utilities to convert between different data formats (JSON, CSV, TXT)
for data export functionality.
"""

import csv
import json
import io
from typing import List, Dict, Any, Optional
import logging

# Configure logging
logger = logging.getLogger(__name__)

def json_to_csv(data: List[Dict[str, Any]], include_headers: bool = True) -> str:
    """
    Convert a list of dictionaries to CSV string format.
    Flattens nested dictionaries with dot notation.
    
    Args:
        data: List of dictionaries to convert
        include_headers: Whether to include column headers
        
    Returns:
        CSV formatted string
    """
    if not data or len(data) == 0:
        logger.warning("Cannot convert empty data to CSV")
        return ""
    
    # Function to flatten nested dictionaries
    def flatten_dict(d, parent_key=''):
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.extend(flatten_dict(v, new_key).items())
            elif isinstance(v, list):
                # Handle lists - serialize to string
                if all(isinstance(i, dict) for i in v):
                    # For lists of dictionaries, flatten each dictionary and aggregate
                    for i, item in enumerate(v):
                        items.extend(flatten_dict(item, f"{new_key}[{i}]").items())
                else:
                    # For simple lists, join elements
                    items.append((new_key, str(v)))
            else:
                items.append((new_key, v))
        return dict(items)
    
    # Flatten all dictionaries in the list
    flattened_data = [flatten_dict(d) for d in data]
    
    # Get all possible headers
    headers = set()
    for d in flattened_data:
        headers.update(d.keys())
    headers = sorted(list(headers))
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    
    if include_headers:
        writer.writeheader()
    
    for row in flattened_data:
        writer.writerow(row)
    
    return output.getvalue()

def json_to_txt(data: List[Dict[str, Any]], include_headers: bool = True) -> str:
    """
    Convert a list of dictionaries to a tab-delimited TXT format.
    Similar to CSV but uses tabs instead of commas.
    
    Args:
        data: List of dictionaries to convert
        include_headers: Whether to include column headers
        
    Returns:
        Tab-delimited text string
    """
    if not data or len(data) == 0:
        logger.warning("Cannot convert empty data to TXT")
        return ""
    
    # Get CSV string first
    csv_string = json_to_csv(data, include_headers)
    
    # Replace commas with tabs
    txt_lines = []
    for line in csv_string.split('\n'):
        # Handle quoted fields correctly
        fields = []
        field = ""
        in_quotes = False
        
        for char in line:
            if char == '"':
                in_quotes = not in_quotes
                field += char
            elif char == ',' and not in_quotes:
                fields.append(field)
                field = ""
            else:
                field += char
                
        if field:  # Add the last field
            fields.append(field)
            
        txt_lines.append('\t'.join(fields))
    
    return '\n'.join(txt_lines)

def ndc_products_to_simplified_format(products: List[Dict[str, Any]], include_additional_fields: bool = False) -> List[Dict[str, Any]]:
    """
    Convert NDC product data to a simplified flat format that's more suitable for CSV/TXT export.
    Uses package NDC as the primary identifier and includes standard default fields.
    
    Args:
        products: List of NDC product dictionaries
        include_additional_fields: Whether to include extra fields beyond the default set
        
    Returns:
        List of simplified flat dictionaries
    """
    simplified = []
    
    for product in products:
        # Extract package NDC information
        packaging = product.get("packaging", [])
        
        # Extract strength from active ingredients
        active_ingredients = product.get("active_ingredients", [])
        strength = ""
        if active_ingredients:
            # Combine strengths if multiple ingredients
            strength_values = [ing.get("strength", "") for ing in active_ingredients if ing.get("strength")]
            strength = "; ".join(strength_values)
        
        # If there's packaging info, create one row per package
        if packaging:
            for package in packaging:
                # Create entry with default fields in the specified order
                simplified_product = {
                    "NDC": package.get("package_ndc", ""),
                    "brand_name": product.get("brand_name", ""),
                    "generic_name": product.get("generic_name", ""),
                    "strength": strength,
                    "route": product.get("route", ""),
                    "dosage_form": product.get("dosage_form", ""),
                    "manufacturer": product.get("openfda", {}).get("manufacturer_name", ["Unknown"])[0] 
                                   if product.get("openfda") else product.get("manufacturer_name", ""),
                    "package_description": package.get("description", ""),
                }
                
                # Include additional fields if requested
                if include_additional_fields:
                    simplified_product.update({
                        "product_ndc": product.get("product_ndc", ""),
                        "marketing_status": product.get("marketing_status", ""),
                        "marketing_start_date": package.get("marketing_start_date", ""),
                    })
                    
                    # Add individual active ingredients information
                    for i, ingredient in enumerate(active_ingredients):
                        simplified_product[f"ingredient_{i+1}_name"] = ingredient.get("name", "")
                        simplified_product[f"ingredient_{i+1}_strength"] = ingredient.get("strength", "")
                
                simplified.append(simplified_product)
        else:
            # No packaging info, create a single row with product NDC
            simplified_product = {
                "NDC": product.get("product_ndc", ""),  # Use product NDC if no package NDC
                "brand_name": product.get("brand_name", ""),
                "generic_name": product.get("generic_name", ""),
                "strength": strength,
                "route": product.get("route", ""),
                "dosage_form": product.get("dosage_form", ""),
                "manufacturer": product.get("openfda", {}).get("manufacturer_name", ["Unknown"])[0] 
                               if product.get("openfda") else product.get("manufacturer_name", ""),
                "package_description": "",
            }
            
            # Include additional fields if requested
            if include_additional_fields:
                simplified_product.update({
                    "marketing_status": product.get("marketing_status", ""),
                    "marketing_start_date": "",
                })
                
                # Add individual active ingredients information
                for i, ingredient in enumerate(active_ingredients):
                    simplified_product[f"ingredient_{i+1}_name"] = ingredient.get("name", "")
                    simplified_product[f"ingredient_{i+1}_strength"] = ingredient.get("strength", "")
            
            simplified.append(simplified_product)
    
    return simplified
