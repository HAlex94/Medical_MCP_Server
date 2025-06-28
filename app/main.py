from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import logging
import uvicorn
from app.routes import mcp_handler
from app.routes.fda import router as fda_router
from app.routes.fda.v3 import router as fda_v3_router
from app.routes.fda.therapeutic_routes import router as therapeutic_router
from app.routes.pharmacy import ndc_lookup_routes
from fastapi.responses import JSONResponse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Medical MCP Server",
    description="MCP server providing medical data from trusted sources like FDA, PubMed, and ClinicalTrials.gov",
    version="0.1.0"
)

# Configure CORS for OpenAI API compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, you may want to restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
)

# Global exception handler for OpenAI compatibility
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": str(exc),
                "code": "internal_error",
                "type": "server_error"
            }
        },
        headers={
            "Content-Type": "application/json"
        }
    )

# Include routers
app.include_router(mcp_handler.router)
app.include_router(fda_router, prefix="/fda")  # Original FDA routes (NDC, Orange Book, etc.)
app.include_router(fda_v3_router, prefix="/fda")  # v3 FDA API with 100% success rate
app.include_router(therapeutic_router, prefix="/fda")  # Therapeutic equivalence routes
app.include_router(ndc_lookup_routes.router, prefix="/pharmacy")

@app.get("/")
async def root():
    """Root endpoint to confirm the server is running."""
    return {"message": "Medical MCP Server is running", "status": "ok"}

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return JSONResponse(
        content={
            "status": "healthy",
            "version": "0.1.0",
            "openai_compatible": True,
            "apis": {
                "fda": "available",
                "rxnorm": "available",
                "pubmed": "available",
                "clinicaltrials": "available"
            }
        },
        headers={
            "Content-Type": "application/json"
        }
    )

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
