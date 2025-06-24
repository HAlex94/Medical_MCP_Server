# Pharmacy Informatics APIs Documentation

This document provides detailed information about the external APIs used in the pharmacy informatics tools, including authentication requirements, rate limits, and fallback strategies.

## FDA NDC Directory API

**Base URL:** https://api.fda.gov/drug/ndc.json  
**Documentation:** https://open.fda.gov/apis/drug/ndc/  
**Authentication:**
- API key optional
- Without key: Limited to 1,000 requests per IP address per day, 40 requests per minute
- With key: Limited to 240,000 requests per day, 120 requests per minute
- Get API key: https://open.fda.gov/apis/authentication/

**Key Endpoints:**
- Product search: `/drug/ndc.json?search=<query>&limit=<limit>`

**Query Parameters:**
- `search`: Search query (e.g., `product_ndc:00071-0155` or `brand_name:Lipitor`)
- `limit`: Maximum number of results (default: 1 if unauthenticated, recommend: 5 for unauthenticated, 100 for authenticated)
- `skip`: Pagination offset
- `api_key`: Optional API key

**Fallback Strategy:**
1. Try with API key
2. If no key or rate limited, use unauthenticated access with smaller result limit
3. If that fails, try alternative search terms (e.g., if searching by NDC fails, try brand name)

## RxNav API (RxNorm APIs)

**Base URL:** https://rxnav.nlm.nih.gov/REST  
**Documentation:** https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html  
**Authentication:**
- No authentication required for most endpoints
- Rate limits not officially documented, but recommendation is max 20 requests per second

**Key Endpoints:**
- Get RxCUI by name: `/rxcui?name={name}`
- Get RxCUI by NDC: `/rxcui?idtype=NDC&id={ndc}`
- Get properties by RxCUI: `/rxcui/{rxcui}/properties`
- Get allProperties by RxCUI: `/rxcui/{rxcui}/allProperties`
- Get NDCs by RxCUI: `/rxcui/{rxcui}/ndcs`
- Get ATC classes: `/rxclass/class/byRxcui?rxcui={rxcui}&relaSource=ATC`

**Important Notes:**
- API returns XML by default; append `.json` to get JSON responses
- Parameter formats are strict and require exact formatting
- Many endpoints require specific relationship sources (`relaSource`)
- Use `allProperties` endpoint only when necessary; `properties` is more efficient

**Fallback Strategy:**
1. Try primary endpoint
2. If that fails, try alternative endpoint with different parameters
3. If all RxNav endpoints fail, fall back to cached data

## PubMed/NCBI API

**Base URL:** https://eutils.ncbi.nlm.nih.gov/entrez/eutils  
**Documentation:** https://www.ncbi.nlm.nih.gov/books/NBK25500/  
**Authentication:**
- API key optional but highly recommended
- Without key: Limited to 3 requests per second
- With key: Limited to 10 requests per second
- Get API key: https://www.ncbi.nlm.nih.gov/account/

**Key Endpoints:**
- Search: `/esearch.fcgi`
- Fetch: `/efetch.fcgi`
- Summary: `/esummary.fcgi`

**Query Parameters:**
- `db`: Database to search (e.g., `pubmed`)
- `term`: Search term
- `retmax`: Maximum number of results (recommend: 5 for unauthenticated, 20 for authenticated)
- `api_key`: Optional API key

**Fallback Strategy:**
1. Try with API key
2. If no key or rate limited, use unauthenticated access with smaller result limit
3. If that fails, fall back to cached data or provide general information without specific references

## Caching Strategy

For all APIs:
1. Cache successful responses with a TTL (time-to-live) based on data type:
   - Drug product information: 7 days
   - Evidence/literature: 1 day
   - RxNorm mappings: 30 days
2. Use memory cache for frequent requests, disk cache for persistence
3. Implement cache warming for common lookups
4. Use stale-while-revalidate strategy when appropriate

## Environment Variables

```
# FDA API
FDA_API_KEY=your_api_key_here

# NCBI/PubMed API
NCBI_API_KEY=your_api_key_here

# Optional configuration
API_CACHE_DIR=/path/to/cache
CACHE_TTL_DAYS=7
MAX_RETRIES=3
REQUEST_TIMEOUT=30
```
