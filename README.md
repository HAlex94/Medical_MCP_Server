# Medical MCP Server

An MCP (Model Context Protocol) server that provides real-time medical information from trusted databases like FDA, PubMed, and ClinicalTrials.gov to ChatGPT and other LLMs.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Setup and Installation](#setup-and-installation)
3. [API Endpoints](#api-endpoints)
   - [Core MCP Endpoints](#mcp-core-endpoints)
   - [FDA Drug Label Information](#drug-label-information)
   - [FDA Orange Book (Generic Drug) Endpoints](#orange-book-generic-drug-endpoints)
   - [FDA Therapeutic Equivalence](#therapeutic-equivalence)
4. [LLM Integration Best Practices](#llm-integration-best-practices)
5. [FDA Label Data Fields](#fda-label-data-fields)
6. [Example LLM Workflows](#example-llm-workflows)
7. [Cloud Deployment](#cloud-deployment)
8. [Testing](#testing)
9. [License & Contributing](#license-and-contributing)

## Project Overview

This server enables ChatGPT and other LLMs to retrieve and respond with real-time medical information by integrating with a custom-built MCP server that connects to authoritative medical databases.

### Features

- **FDA Drug Information**: Search medications by name, NDC, or active ingredient
  - LLM-optimized endpoints with multi-stage fallback search strategies
  - Field aliasing for more intuitive queries
  - Robust error handling and rate limit awareness
  - Consistent, predictable JSON response formats
- **Orange Book & Therapeutic Equivalence**: Find generic alternatives and reference drugs
  - Multi-parameter search with flexible filters
  - TE code grouping and filtering capabilities
  - Detailed diagnostic information for improved transparency
- **RxNorm Integration**: Cross-reference medications between different coding systems
- **PubMed Article Search**: Find medical research papers by keyword, topic, or author
- **Clinical Trials Search**: Look up active or completed clinical trials by condition
- **FHIR Resource Generation**: Convert medication data to standard FHIR resources
- **API Caching System**: Reduce API calls with intelligent memory and disk caching

## Setup and Installation

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Local Development

1. Clone the repository:

```bash
git clone <repository-url>
cd medical-mcp-server
```

2. Set up a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file from the example:

```bash
cp .env.example .env
# Edit .env with your API keys if needed (API keys are optional, unauthenticated access is supported)
```

**Environment Variables:**

```
# API Keys (optional)
FDA_API_KEY=your_fda_api_key
NCBI_API_KEY=your_ncbi_api_key

# API Cache Settings
API_CACHE_DIR=app/cache
CACHE_TTL_SECONDS=604800  # 7 days

# Request Settings
MAX_RETRIES=3
REQUEST_TIMEOUT=30
```

5. Run the server locally:

```bash
python -m app.main
```

The server will be available at `http://localhost:8000`

## Cloud Deployment

This project is configured for deployment on [Render](https://render.com/) using the provided `render.yaml` file:

1. Create a Render account if you don't have one
2. Create a new Web Service and connect your repository
3. Select "Use render.yaml from repository" during setup
4. Add any required environment variables

## API Endpoints

### MCP Core Endpoints

- `GET /`: Health check to confirm the server is running
- `POST /resources/list`: MCP endpoint that lists available medical data resources
- `POST /resources/get`: MCP endpoint to get details about a specific resource
- `POST /resources/execute`: MCP endpoint to execute a resource function with arguments

### FDA API Endpoints

#### Drug Label Information

- `GET /fda/label/llm-discover`: LLM-optimized endpoint to retrieve drug label fields
  - **Parameters**:
    - `field`: Label field to retrieve (or comma-separated fields, or "ALL")
    - `ndc`: NDC code (or comma-separated list for fallback)
    - `name`: Drug name (optional fallback if NDC fails)
  - **Features**:
    - Field aliases: `black_box_warning` → `boxed_warning`, etc.
    - Multi-stage fallback search (NDC → name → substance → exists)
    - Detailed response metadata with search diagnostics

- `GET /fda/label/search`: Standard endpoint for drug label search
  - **Parameters**:
    - `name`: Drug name (brand or generic)
    - `fields`: Comma-separated list of label fields to return (optional)

#### Orange Book (Generic Drug) Endpoints

- `GET /fda/orange-book/search`: Search the FDA Orange Book
  - **Parameters**:
    - `ndc`: NDC product code
    - `name`: Drug name
    - `active_ingredient`: Active ingredient name
    - `application_number`: FDA application number
  - **Features**:
    - Multiple search strategies with automatic fallback
    - Rate limit awareness with helpful diagnostics
    - Detailed metadata about the search process

- `GET /fda/orange-book/equivalent-products`: Find therapeutically equivalent products
  - **Parameters**:
    - `ndc`: Reference NDC to find equivalents for
    - `te_code`: Optional filter by therapeutic equivalence code (e.g., "AB", "AB1")
    - `fields`: Optional comma-separated fields to include
  - **Features**:
    - Automatic reference product identification
    - TE code filtering for targeted equivalent searches
    - Detailed reference product metadata

#### Therapeutic Equivalence

- `GET /fda/therapeutic-equivalence`: Find reference and equivalent drugs
  - **Parameters**:
    - `name`: Drug name to search for
    - `ndc`: NDC code to search for
    - `active_ingredient`: Active ingredient to search for
    - `te_code`: Filter by specific therapeutic equivalence code (e.g., 'AB', 'AB1')
    - `group_by_te_code`: Group equivalent products by their TE code (boolean)
    - `fields`: Comma-separated fields to include in response
  - **Features**:
    - Multi-strategy lookup (NDC → name → active ingredient)
    - Name normalization and suffix cleaning
    - Full search traceability with enhanced diagnostics
    - Reference drug detection via multiple signals
    - TE code filtering and grouping for organized results
    - Multiple reference drug warning detection
    - Comprehensive equivalent product listings with TE codes

## LLM Integration Best Practices

Follow these best practices when integrating the Medical MCP Server's FDA APIs with language models:

### 1. Use Enhanced Endpoints for LLM Workflows

Prefer the LLM-optimized endpoints for most workflows:

- Use `/fda/label/llm-discover` instead of basic label endpoints
- Use `/fda/orange-book/search` with enhanced metadata
- Use `/fda/therapeutic-equivalence` with grouping and filtering options

### 2. Leverage Multi-Parameter Searches

Our enhanced endpoints support multiple search parameters with intelligent fallback:

```python
# Better approach - let the backend handle fallbacks
response = await client.get("/fda/label/llm-discover", params={
    "ndc": "00071-0155-23,00071-0155-24",  # Try multiple NDCs
    "name": "Lipitor",                     # Fallback to name search
    "field": "boxed_warning,indications_and_usage"  # Get multiple fields
})
```

### 3. Utilize Field Aliases

The enhanced endpoints support common field name variations:

```
"black_box_warning" → "boxed_warning"
"warnings" → "warnings_and_precautions"
"dosage" → "dosage_and_administration"
```

### 4. Parse Response Metadata

Always check response metadata for:

- `search_strategy`: Which strategy ultimately succeeded
- `strategies_attempted`: All strategies that were tried
- `available_fields`: All fields available in the response
- Rate limiting information and diagnostic details

### 5. Handle Graceful Degradation

The enhanced APIs will try multiple fallback strategies before failing:

```python
if response.json().get("success"):
    # Process results normally
    products = response.json().get("products")
    message = response.json().get("message")
else:
    # Check for partial results
    partial_results = response.json().get("metadata", {}).get("partial_results")
    if partial_results:
        # Process partial results
        print(f"Showing partial results: {response.json().get('message')}")
    else:
        # Show failure message
        print(f"Error: {response.json().get('message')}")
```

### 6. Use TE Code Filtering and Grouping

For therapeutic equivalence endpoints, use the TE code filtering and grouping features:

```python
# Group equivalent products by their TE code
response = await client.get("/fda/therapeutic-equivalence", params={
    "name": "Lipitor",
    "group_by_te_code": True,
    "te_code": "AB"  # Only show AB-rated equivalents
})

# Process grouped results
if response.json().get("success") and response.json().get("grouped_by_te_code"):
    for te_code, products in response.json().get("grouped_by_te_code").items():
        print(f"TE Code {te_code}: {len(products)} products")
```

## LLM-Optimized API Design

Our FDA API endpoints follow these design principles optimized for Large Language Model consumption:

### Consistency & Predictability
- **Uniform Response Structure**: All endpoints return consistent JSON shapes regardless of success/failure
- **Standardized Metadata**: Each response includes query details, search strategies, and available fields

### Robustness & Resilience
- **Multi-Stage Fallback**: Endpoints attempt multiple search strategies when the primary strategy fails
- **Graceful Degradation**: Even partial results are returned with clear explanations
- **Detailed Diagnostics**: Each response includes information about what was tried and why

### Flexibility & Usability
- **Field Aliases**: Common variations and synonyms are mapped to canonical names
- **Multi-Parameter Support**: Multiple search parameters with intelligent priority handling
- **Explicit Error Messaging**: Clear error messages with actionable suggestions

### Response Structure Example

```json
{
  "success": true,
  "query": "Therapeutic equivalents for Wellbutrin XL (NDC: 12345-6789)",
  "search_strategy": "active_ingredient_and_form_search",
  "strategies_attempted": [
    "reference_product_search", 
    "te_code_filter:AB"
  ],
  "available_fields": ["brand_name", "manufacturer", "ndc", "te_code", "strength"],
  "metadata": {
    "reference_product": {
      "ndc": "12345-6789",
      "name": "Wellbutrin XL"
    },
    "rate_limited": false
  },
  "products": [/* Array of products */],
  "message": "Found 3 therapeutically equivalent products"
}
```

## FDA Label Data Fields

The FDA label endpoints support retrieving the following common fields:

| Field Name | Description |
|------------|-------------|
| `active_ingredient` | Active ingredients in the drug |
| `inactive_ingredient` | Inactive ingredients/excipients |
| `indications_and_usage` | FDA-approved uses for the drug |
| `boxed_warning` | Critical safety warnings (black box) |
| `warnings` | Important safety warnings |
| `warnings_and_precautions` | Detailed precautions |
| `contraindications` | Situations where the drug should not be used |
| `adverse_reactions` | Side effects |
| `drug_interactions` | How the drug interacts with other medications |
| `dosage_and_administration` | Dosing information |
| `pregnancy` | Safety and risks during pregnancy |
| `clinical_pharmacology` | How the drug works in the body |

### Example LLM Queries

- "What are the indications for apixaban?"
- "What are the warnings for ceftriaxone?"
- "What are the active ingredients in Eliquis?"
- "Find therapeutic equivalents for Lipitor that are AB-rated"
- "Show me dosage information for metformin"

## Example LLM Workflows

### Drug Safety Information

```python
async def get_drug_safety_info(drug_name_or_ndc):
    """Example function showing best practices for retrieving drug safety information."""
    # Use the LLM-optimized endpoint
    response = await client.get("/fda/label/llm-discover", params={
        "name": drug_name_or_ndc,  # Will also try this as NDC if it looks like one
        "field": "boxed_warning,warnings_and_precautions,adverse_reactions"
    })
    
    data = response.json()
    if data.get("success"):
        safety_info = {
            "drug_name": data.get("meta", {}).get("drug_name"),
            "boxed_warning": data.get("results", {}).get("boxed_warning"),
            "warnings": data.get("results", {}).get("warnings_and_precautions"),
            "adverse_reactions": data.get("results", {}).get("adverse_reactions"),
        }
        return safety_info
    else:
        # Check search diagnostics for clues
        search_methods = data.get("meta", {}).get("search_methods_tried", [])
        return {
            "error": data.get("message"), 
            "search_attempts": search_methods
        }
```

## ChatGPT Integration

1. Host this server on a cloud platform that provides a public HTTPS endpoint
2. Register the server URL as a Custom Action or Plugin within ChatGPT
3. ChatGPT will automatically call the MCP server in response to relevant medical questions

## Testing

Run tests with:

```bash
pytest
```

## License and Contributing

This project is available under the MIT License.

Contributions are welcome! Please feel free to submit a Pull Request.
