# FDA Label Data Feature

This feature allows for retrieving detailed drug label information from the FDA directly through the Medical MCP Server, similar to the PillQ app functionality.

## Features

- **Direct Label Data Retrieval**: Get comprehensive drug label information directly from the FDA database
- **Field Selection**: Request specific label sections like indications, active ingredients, warnings, etc.
- **MCP Protocol Integration**: Access label data through ChatGPT and other LLM integrations
- **Fallback Search Mechanisms**: Multiple search approaches to maximize data retrieval success
- **Robust Error Handling**: Clear messaging when drugs cannot be found

## API Endpoints

### Direct API Endpoint
```
GET /fda/label/search
```

**Parameters**:
- `name`: Drug name (brand or generic)
- `fields`: Comma-separated list of label fields to return (optional)

**Example**:
```
GET /fda/label/search?name=apixaban&fields=indications_and_usage,warnings,active_ingredient
```

### MCP Protocol Endpoint
```
POST /resources/fda/label/data/execute
```

**Request Body**:
```json
{
  "arguments": {
    "name": "apixaban",
    "fields": "indications_and_usage,warnings,active_ingredient"
  }
}
```

## Common Label Fields

- `active_ingredient`: Active ingredients in the drug
- `inactive_ingredient`: Inactive ingredients/excipients
- `indications_and_usage`: FDA-approved uses for the drug
- `warnings`: Important safety warnings
- `warnings_and_cautions`: Detailed precautions
- `contraindications`: Situations where the drug should not be used
- `adverse_reactions`: Side effects
- `drug_interactions`: How the drug interacts with other medications
- `dosage_and_administration`: Dosing information

## Example ChatGPT Queries

- "What are the indications for apixaban?"
- "What are the warnings for ceftriaxone?"
- "What are the active ingredients in Eliquis?"

## Implementation Notes

This feature directly queries the FDA label database using the same approach as the PillQ app, with several improvements:
- Normalized drug name handling
- Multiple search strategies (generic name, brand name, substance name)
- FDA API key support for higher rate limits
- Robust error handling and user-friendly messages
