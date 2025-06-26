"""
Therapeutic Equivalence Routes

Specialized routes for retrieving therapeutic equivalence data from FDA APIs,
designed for consistent LLM consumption.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException
import httpx
import os
import logging
from pydantic import BaseModel
from app.utils.api_clients import make_request
from app.utils.shared import get_fda_api_key

router = APIRouter()
logger = logging.getLogger(__name__)

# Models for the response
class EquivalentProduct(BaseModel):
    """Model for a therapeutically equivalent product"""
    brand_name: str
    manufacturer: Optional[str] = None
    ndc: Optional[str] = None
    application_number: Optional[str] = None
    te_code: Optional[str] = None
    dosage_form: Optional[str] = None
    strength: Optional[str] = None
    reference_drug: Optional[bool] = False

class TherapeuticEquivalenceResponse(BaseModel):
    """Response model for therapeutic equivalence data"""
    brand_name: Optional[str] = None
    active_ingredient: Optional[str] = None
    ndc: Optional[str] = None
    te_codes: List[str] = []
    reference_drug: bool = False
    equivalent_products: List[EquivalentProduct] = []
    message: Optional[str] = None

async def find_reference_product(name=None, active_ingredient=None, ndc=None):
    """Find a reference product using different search strategies"""
    search_params = []
    if name:
        search_params.append(f"openfda.brand_name:\"{name}\"")
    if active_ingredient:
        search_params.append(f"openfda.generic_name:\"{active_ingredient}\"")
    if ndc:
        search_params.append(f"openfda.product_ndc:\"{ndc}\"")
    
    # Try each search parameter individually for best results
    reference_product = None
    for search_query in search_params:
        try:
            url = f"https://api.fda.gov/drug/drugsfda.json?search={search_query}&limit=10"
            api_key = get_fda_api_key()
            if api_key:
                url += f"&api_key={api_key}"
                
            response = await make_request(url)
            
            # Process results to find reference products
            if response and "results" in response:
                for product_data in response["results"]:
                    if "products" in product_data:
                        for product in product_data["products"]:
                            # Look for reference drugs
                            if product.get("reference_drug") == "Yes" or product.get("reference_standard") == "Yes":
                                sponsor_name = product_data.get("sponsor_name", "Unknown")
                                brand = product.get("brand_name", name)
                                
                                reference_product = {
                                    "brand_name": brand,
                                    "manufacturer": sponsor_name,
                                    "application_number": product_data.get("application_number"),
                                    "te_code": product.get("te_code"),
                                    "reference_drug": True
                                }
                                
                                # If we found a product that matches our search exactly, use it
                                if (not name or name.lower() in brand.lower() or 
                                    brand.lower() in name.lower()):
                                    return reference_product
                    
                # If we didn't find an exact match but have any reference product, use it
                if reference_product:
                    return reference_product
                    
                # If no reference product, just use the first product
                if not reference_product and response["results"] and "products" in response["results"][0]:
                    product = response["results"][0]["products"][0]
                    sponsor_name = response["results"][0].get("sponsor_name", "Unknown")
                    return {
                        "brand_name": product.get("brand_name", name or "Unknown"),
                        "manufacturer": sponsor_name,
                        "application_number": response["results"][0].get("application_number"),
                        "te_code": product.get("te_code"),
                        "reference_drug": product.get("reference_drug") == "Yes"
                    }
        except Exception as e:
            logger.error(f"Error finding reference product with query {search_query}: {str(e)}")
            continue
    
    return None

async def find_equivalent_products(reference_product, active_ingredient=None):
    """Find therapeutically equivalent products for a reference product"""
    if not reference_product:
        return []
        
    equivalent_products = []
    
    # Try to find by active ingredient first (most reliable)
    if active_ingredient:
        search_query = f"openfda.generic_name:\"{active_ingredient}\""
    else:
        # If no active ingredient specified, try to infer from brand name
        search_query = f"openfda.brand_name:\"{reference_product['brand_name']}\""
    
    try:
        url = f"https://api.fda.gov/drug/drugsfda.json?search={search_query}&limit=100"
        api_key = get_fda_api_key()
        if api_key:
            url += f"&api_key={api_key}"
            
        response = await make_request(url)
        
        if response and "results" in response:
            for product_data in response["results"]:
                if "products" in product_data:
                    sponsor_name = product_data.get("sponsor_name", "Unknown")
                    for product in product_data["products"]:
                        # Skip if it's the reference product
                        if (product.get("brand_name") == reference_product.get("brand_name") and
                            product_data.get("application_number") == reference_product.get("application_number")):
                            continue
                            
                        # Only include products with therapeutic equivalence codes
                        if product.get("te_code"):
                            # Extract strength and dosage form
                            strength = None
                            if "active_ingredients" in product and product["active_ingredients"]:
                                if isinstance(product["active_ingredients"], list):
                                    strength = product["active_ingredients"][0].get("strength")
                                else:
                                    strength = product["active_ingredients"].get("strength")
                                    
                            if not strength:
                                strength = product.get("strength")
                                
                            # Get dosage form
                            dosage_form = None
                            if isinstance(product.get("dosage_form"), dict):
                                dosage_form = product["dosage_form"].get("form")
                            else:
                                dosage_form = product.get("dosage_form")
                                
                            # Get NDC if available
                            ndc = None
                            if "openfda" in product_data and "product_ndc" in product_data["openfda"]:
                                if isinstance(product_data["openfda"]["product_ndc"], list):
                                    ndc = product_data["openfda"]["product_ndc"][0]
                            
                            # Add to equivalent products
                            equivalent_products.append(EquivalentProduct(
                                brand_name=product.get("brand_name", "Generic"),
                                manufacturer=sponsor_name,
                                ndc=ndc,
                                application_number=product_data.get("application_number"),
                                te_code=product.get("te_code"),
                                dosage_form=dosage_form,
                                strength=strength,
                                reference_drug=product.get("reference_drug") == "Yes"
                            ))
    except Exception as e:
        logger.error(f"Error finding equivalent products: {str(e)}")
    
    return equivalent_products

@router.get("/therapeutic-equivalence", response_model=TherapeuticEquivalenceResponse)
async def get_therapeutic_equivalence(
    name: Optional[str] = Query(None, description="Brand name of the drug"),
    ndc: Optional[str] = Query(None, description="NDC code of the drug"),
    active_ingredient: Optional[str] = Query(None, description="Active ingredient of the drug")
):
    """
    Get therapeutic equivalence data for a drug by name, NDC, or active ingredient.
    Returns the reference drug and all therapeutically equivalent products.
    """
    if not name and not ndc and not active_ingredient:
        raise HTTPException(status_code=400, detail="At least one search parameter (name, ndc, or active_ingredient) is required")
        
    try:
        # Step 1: Find a reference product
        reference_product = await find_reference_product(name, active_ingredient, ndc)
        
        # Step 2: Find equivalent products
        equivalent_products = await find_equivalent_products(reference_product, active_ingredient)
            
        # Step 3: Collect unique TE codes
        te_codes = set()
        if reference_product and reference_product.get("te_code"):
            te_codes.add(reference_product["te_code"])
            
        for product in equivalent_products:
            if product.te_code:
                te_codes.add(product.te_code)
        
        # Create the response
        response = TherapeuticEquivalenceResponse(
            brand_name=reference_product.get("brand_name") if reference_product else name,
            active_ingredient=active_ingredient,
            ndc=ndc,
            te_codes=list(te_codes),
            reference_drug=reference_product.get("reference_drug", False) if reference_product else False,
            equivalent_products=equivalent_products
        )
        
        # Add message if no products found
        if not equivalent_products:
            if reference_product:
                response.message = "Found reference drug but no therapeutically equivalent products"
            else:
                response.message = "No reference drug or equivalent products found"
        
        return response
    except Exception as e:
        logger.error(f"Error getting therapeutic equivalence: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving therapeutic equivalence data: {str(e)}")
