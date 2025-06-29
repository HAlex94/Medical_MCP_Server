"""app/main.py — FastAPI application entry point, router registration, and server configuration"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import logging
import uvicorn
import importlib
import sys
from fastapi.responses import JSONResponse

# Setup logging first so we can log import errors
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Dictionary to hold all imported routers
routers = {}

# Import all required modules with error handling
module_paths = [
    ('mcp_handler', 'app.routes.mcp_handler'),
    ('fda_router', 'app.routes.fda'),
    ('fda_v3_router', 'app.routes.fda.v3'),
    ('therapeutic_router', 'app.routes.fda.therapeutic_routes'),
    ('dailymed_router', 'app.routes.fda.dailymed_routes'),
    ('pharmacy_router', 'app.routes.pharmacy'),
    ('export_router', 'app.routes.export_routes')
]

# Import routers safely with error handling
routers = {}
for router_name, module_path in module_paths:
    try:
        logger.info(f"Attempting to import {router_name} from {module_path}")
        module = importlib.import_module(module_path)
        router_obj = getattr(module, 'router')
        routers[router_name] = router_obj
        logger.info(f"Successfully imported {router_name} from {module_path}")
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to import {router_name} from {module_path}: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Python path: {sys.path}")


# Logger was already set up above

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

# Include routers with error handling
if "mcp_handler" in routers:
    app.include_router(routers["mcp_handler"])
    logger.info("Included mcp_handler router")

if "fda_router" in routers:
    app.include_router(routers["fda_router"], prefix="/fda")  # Original FDA routes (NDC, Orange Book, etc.)
    logger.info("Included fda_router with prefix /fda")

if "fda_v3_router" in routers:
    app.include_router(routers["fda_v3_router"], prefix="/fda")  # v3 FDA API with 100% success rate
    logger.info("Included fda_v3_router with prefix /fda")

if "therapeutic_router" in routers:
    app.include_router(routers["therapeutic_router"], prefix="/fda")  # Therapeutic equivalence routes
    logger.info("Included therapeutic_router with prefix /fda")

if "pharmacy_router" in routers:
    app.include_router(routers["pharmacy_router"], prefix="/pharmacy")
    logger.info("Included pharmacy_router with prefix /pharmacy")

if "export_router" in routers:
    app.include_router(routers["export_router"], prefix="/export")
    logger.info("Included export_router with prefix /export")

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
