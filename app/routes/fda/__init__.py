from fastapi import APIRouter

from .label_routes import router as label_router
from .ndc_routes import router as ndc_router
from .orange_book_routes import router as orange_book_router

router = APIRouter(prefix="/fda")

# Include all FDA-related routes
router.include_router(label_router)
router.include_router(ndc_router)
router.include_router(orange_book_router)
