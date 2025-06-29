"""
Session Bootstrap for Medical MCP Server

This script displays key information about the Medical MCP Server application
to provide a quick overview of the system state and configuration.
"""

import sys
import importlib.metadata
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

def print_separator():
    """Print a separator line for readability"""
    print("\n" + "=" * 80 + "\n")

def get_project_root():
    """Get the project root directory"""
    # Start from current directory and move up until we find main.py
    current = Path(__file__).resolve().parent
    while current.name and not (current / "app" / "main.py").exists():
        current = current.parent
    return current

def print_system_info():
    """Print system and environment information"""
    print_separator()
    logger.info("🔧 SYSTEM INFORMATION")
    logger.info(f"Python version: {sys.version}")
    
    # Print key package versions
    try:
        fastapi_version = importlib.metadata.version("fastapi")
        httpx_version = importlib.metadata.version("httpx")
        uvicorn_version = importlib.metadata.version("uvicorn")
        
        logger.info(f"FastAPI: {fastapi_version}")
        logger.info(f"HTTPX: {httpx_version}")
        logger.info(f"Uvicorn: {uvicorn_version}")
    except importlib.metadata.PackageNotFoundError as e:
        logger.warning(f"Could not determine version: {e}")

def print_app_structure():
    """Print application structure information"""
    print_separator()
    logger.info("📂 APPLICATION STRUCTURE")
    
    # Try to import the FastAPI app to list routes
    try:
        project_root = get_project_root()
        sys.path.insert(0, str(project_root))
        
        from app.main import app, routers
        
        # List registered routers
        logger.info("Registered routers:")
        for router_name, router in routers.items():
            logger.info(f"  - {router_name}")
        
        # List key endpoints
        logger.info("\nKey API endpoints:")
        for route in app.routes:
            if hasattr(route, "path") and not str(route.path).startswith("/docs") and not str(route.path).startswith("/openapi"):
                logger.info(f"  - {route.path}")
                
    except ImportError as e:
        logger.warning(f"Could not import app: {e}")
        logger.info("Run this script from the project root for full information.")

def print_recent_changes():
    """Print recent changes from AI_CHANGELOG"""
    print_separator()
    logger.info("📝 RECENT CHANGES")
    
    try:
        project_root = get_project_root()
        changelog_path = project_root / "ai_documentation" / "AI_CHANGELOG_NEW.md"
        
        if changelog_path.exists():
            with open(changelog_path, 'r') as f:
                # Read file and extract recent changes section
                content = f.read()
                if "## Recent Changes" in content:
                    recent_changes = content.split("## Recent Changes")[1].split("##")[0].strip()
                    logger.info(recent_changes)
                else:
                    logger.info("Recent changes section not found in changelog.")
        else:
            logger.warning("AI_CHANGELOG_NEW.md not found.")
    except Exception as e:
        logger.warning(f"Error reading changelog: {e}")

def main():
    """Main function to run the bootstrap"""
    logger.info("🚀 MEDICAL MCP SERVER - SESSION BOOTSTRAP")
    
    print_system_info()
    print_app_structure()
    print_recent_changes()
    
    print_separator()
    logger.info("Bootstrap completed. You are ready to start development.")
    logger.info("Remember to check PROJECT_MAP.md for a complete project overview.")
    print_separator()

if __name__ == "__main__":
    main()
