# Medical MCP Server Project Map

## Core Components
- `app/main.py` - FastAPI application entry point and router configuration
- `app/config.py` - Environment and application configuration 

## API Routes
### FDA Data
- `app/routes/fda/__init__.py` - FDA router initialization and configuration
- `app/routes/fda/therapeutic_routes.py` - Therapeutic equivalence endpoints
- `app/routes/fda/ndc_routes.py` - NDC database search endpoints
- `app/routes/fda/orange_book_routes.py` - Orange Book data retrieval endpoints
- `app/routes/fda/dailymed_routes.py` - DailyMed fallback data endpoints
- `app/routes/fda/v3/` - Version 3 FDA API endpoints

### Pharmacy Services
- `app/routes/pharmacy/ndc_lookup_routes.py` - NDC lookup endpoints
- `app/routes/pharmacy/bulk_ndc_routes.py` - Bulk NDC data operations

### Other Routes
- `app/routes/export_routes.py` - Data export functionality endpoints
- `app/routes/mcp_handler.py` - MCP protocol request handlers
- `app/routes/tools/` - Utility endpoints and tools

## Utilities
- `app/utils/api_clients.py` - Base HTTP client functionality
- `app/utils/api_cache.py` - Caching mechanisms for API responses
- `app/utils/dailymed_client.py` - DailyMed API client for fallback operations
- `app/utils/dailymed/` - DailyMed data processing utilities

## Testing
- `tests/` - Integration and unit tests for the application

## Scripts
- `scripts/` - Utility scripts, demos, and tools

## Documentation
- `app/docs/` - API documentation
- `ai_documentation/` - AI-assisted development documentation
