import asyncio
import json
import sys
import httpx
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Test both the direct FDA endpoint and the MCP routing
async def test_fda_drug_search():
    """Test the FDA drug search endpoint directly and through MCP routing"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        base_url = "http://127.0.0.1:8000"  # Local testing
        drug_name = "apixaban"

        # Test 1: Direct endpoint call
        logger.info(f"Testing direct endpoint call with drug name: {drug_name}")
        try:
            direct_response = await client.get(
                f"{base_url}/fda/ndc/compact_search?name={drug_name}&limit=5"
            )
            logger.info(f"Direct endpoint status: {direct_response.status_code}")
            if direct_response.status_code == 200:
                result = direct_response.json()
                logger.info(f"Total results: {result.get('total_results')}")
                logger.info(f"Displayed results: {result.get('displayed_results')}")
                if result.get('products'):
                    logger.info("First product details:")
                    logger.info(json.dumps(result['products'][0], indent=2))
                else:
                    logger.error("No products found in direct endpoint response")
            else:
                logger.error(f"Direct endpoint error: {direct_response.text}")
        except Exception as e:
            logger.error(f"Direct endpoint exception: {str(e)}")

        # Test 2: MCP routing call
        logger.info("\nTesting MCP routing call")
        try:
            mcp_response = await client.post(
                f"{base_url}/resources/execute",
                json={
                    "uri": "fda/drug/search",
                    "arguments": {
                        "name": drug_name,
                        "limit": 5
                    }
                }
            )
            logger.info(f"MCP endpoint status: {mcp_response.status_code}")
            if mcp_response.status_code == 200:
                result = mcp_response.json()
                if "result" in result and "products" in result["result"]:
                    logger.info(f"Total results: {result['result'].get('total_results')}")
                    logger.info(f"Displayed results: {result['result'].get('displayed_results')}")
                    if result["result"]["products"]:
                        logger.info("First product details:")
                        logger.info(json.dumps(result["result"]["products"][0], indent=2))
                    else:
                        logger.error("No products found in MCP response")
                else:
                    logger.error(f"Unexpected MCP response structure: {json.dumps(result, indent=2)}")
            else:
                logger.error(f"MCP endpoint error: {mcp_response.text}")
        except Exception as e:
            logger.error(f"MCP endpoint exception: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_fda_drug_search())
