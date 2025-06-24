from fastapi import FastAPI
import logging
import uvicorn
from app.routes import mcp_handler

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

# Include MCP routes
app.include_router(mcp_handler.router, prefix="")

@app.get("/")
async def root():
    """Root endpoint to confirm the server is running."""
    return {"message": "Medical MCP Server is running", "status": "ok"}

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
