from fastapi import APIRouter

# Create a pharmacy router
router = APIRouter()

# Import all pharmacy-related routes
from .ndc_lookup_routes import router as ndc_lookup_router

# Include routers
router.include_router(ndc_lookup_router, tags=["Pharmacy"])