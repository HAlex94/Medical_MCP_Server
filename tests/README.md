# DailyMed Scraper Tests

This directory contains tests for the DailyMed scraper module.

## Test Structure

- **Unit Tests**: Test individual components without external dependencies
  - `test_parsing.py`: Tests for HTML parsing functions using sample HTML snippets
  - `test_search.py`: Tests for search functionality (requires network)

- **Integration Tests**: Test end-to-end functionality
  - `test_integration.py`: Tests that use real DailyMed API calls

## Running Tests

### Run all tests:

```bash
pytest
```

### Run only unit tests (skip integration tests):

```bash
pytest -m "not integration"
```

### Run only integration tests:

```bash
pytest -m "integration"
```

### Run tests for a specific module:

```bash
pytest tests/test_parsing.py
```

## Test Design

1. **Unit tests** use small, controlled input to test specific functionality
   - Static HTML for testing parsers
   - Parameter variations for search functions

2. **Integration tests** verify that different components work together correctly
   - Test the entire pipeline from search to data extraction
   - Verify that important drug information is extracted correctly

## Future Improvements

- Add mocking for HTTP requests to make all tests offline-capable
- Create fixture data files with pre-captured responses for common drugs
- Add more specific tests for error conditions and edge cases
