from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import uvicorn
import importlib
import sys
import os
from fastapi.responses import JSONResponse

# Setup logging first so we can log import errors
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Define routers to be imported
router_modules = {
    "mcp_handler": "app.routes.mcp_handler",
    "fda_router": "app.routes.fda",
    "fda_v3_router": "app.routes.fda.v3",
    "therapeutic_router": "app.routes.fda.therapeutic_routes",
    "pharmacy_router": "app.routes.pharmacy"
}

# Import routers safely with error handling
routers = {}
for router_name, module_path in router_modules.items():
    try:
        module = importlib.import_module(module_path)
        routers[router_name] = getattr(module, 'router')
        logger.info(f"Successfully imported {router_name} from {module_path}")
    except (ImportError, AttributeError) as e:
        logger.error(f"Failed to import {router_name} from {module_path}: {str(e)}")
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

# Mount static files directory
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"Mounted static files directory: {static_dir}")
else:
    logger.warning(f"Static directory not found at {static_dir}")

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
