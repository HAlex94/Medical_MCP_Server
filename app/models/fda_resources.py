from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class DrugSearchParams(BaseModel):
    name: Optional[str] = Field(None, description="Brand or generic name of the drug")
    manufacturer: Optional[str] = Field(None, description="Name of the manufacturer")
    active_ingredient: Optional[str] = Field(None, description="Active ingredient in the drug")
    ndc: Optional[str] = Field(None, description="National Drug Code")
    limit: int = Field(10, description="Maximum number of results to return (default: 10)")
    skip: int = Field(0, description="Number of results to skip for pagination (default: 0)")

class ActiveIngredient(BaseModel):
    name: str = Field(..., description="Name of the active ingredient")
    strength: str = Field(..., description="Strength of the active ingredient")

class DrugProduct(BaseModel):
    product_ndc: str = Field(..., description="National Drug Code for the product")
    brand_name: Optional[str] = Field(None, description="Brand name of the drug")
    generic_name: Optional[str] = Field(None, description="Generic name of the drug")
    dosage_form: Optional[str] = Field(None, description="Dosage form (e.g., tablet, capsule)")
    route: Optional[List[str]] = Field(None, description="Route of administration")
    marketing_status: Optional[str] = Field(None, description="Marketing status (e.g., Prescription)")
    active_ingredients: List[ActiveIngredient] = Field([], description="Active ingredients and their strengths")
    manufacturer_name: Optional[str] = Field(None, description="Name of the manufacturer")

class DrugSearchResponse(BaseModel):
    total_results: int = Field(..., description="Total number of results matching the query")
    displayed_results: int = Field(..., description="Number of results being displayed")
    products: List[DrugProduct] = Field(..., description="List of drug products")
