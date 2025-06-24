# Medical MCP Server

An MCP (Model Context Protocol) server that provides real-time medical information from trusted databases like FDA, PubMed, and ClinicalTrials.gov to ChatGPT.

## Project Overview

This server enables ChatGPT—including its mobile app—to retrieve and respond with real-time medical information by integrating with a custom-built, cloud-hosted MCP server that connects to authoritative medical databases.

### Features

- **FDA Drug Information**: Search medications by name, NDC, or active ingredient
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

- `GET /`: Health check to confirm the server is running
- `POST /resources/list`: MCP endpoint that lists available medical data resources
- `POST /resources/get`: MCP endpoint to get details about a specific resource
- `POST /resources/execute`: MCP endpoint to execute a resource function with arguments

## ChatGPT Integration

1. Host this server on a cloud platform that provides a public HTTPS endpoint
2. Register the server URL as a Custom Action or Plugin within ChatGPT
3. ChatGPT will automatically call the MCP server in response to relevant medical questions

## Testing

Run tests with:

```bash
pytest
```

## License

This project is available under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
