"""
Deprecated FDA API Routes

This package contains deprecated FDA API implementations that are still used
by some parts of the system but are planned for eventual removal.

Do not add new functionality here - use the v3 API instead.
"""

from fastapi import APIRouter

# Create a router for deprecated endpoints
router = APIRouter()

# Import all deprecated routes that are still in use
from .label_info_routes import router as label_info_router

# Include routers
router.include_router(label_info_router, tags=["FDA-Deprecated"])
