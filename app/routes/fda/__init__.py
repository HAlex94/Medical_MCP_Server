from fastapi import APIRouter

# Import active routes - no longer include deprecated routes
from .ndc_routes import router as ndc_router
from .orange_book_routes import router as orange_book_router
from .therapeutic_routes import router as therapeutic_router

# Main FDA router - prefix is added in main.py, do NOT add prefix here
router = APIRouter()

# Include active FDA-related routes
# Note: Drug label routes are now handled by the v3 API (imported directly in main.py)
router.include_router(ndc_router, tags=["FDA"])
router.include_router(orange_book_router, tags=["FDA"])
router.include_router(therapeutic_router, tags=["FDA"])
