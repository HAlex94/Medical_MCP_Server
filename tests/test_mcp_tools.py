"""
Tests for MCP Tool Functions

This module contains tests for the medical data tools used by our MCP server.
"""
import unittest
import asyncio
from app.routes.tools import fda, pubmed, trials

class TestFDATools(unittest.TestCase):
    """Tests for FDA medication lookup tools."""
    
    def test_search_medication_structure(self):
        """Test that the search_medication function has the expected structure."""
        self.assertTrue(hasattr(fda, 'search_medication'))
        self.assertTrue(callable(fda.search_medication))
    
    def test_search_medication_results(self):
        """Test that search_medication returns results in the expected format."""
        # Run async function in a synchronous test
        result = asyncio.run(fda.search_medication("ibuprofen", limit=2))
        
        # Check response structure
        self.assertIn("status", result)
        self.assertIn("message", result)
        self.assertIn("query", result)
        self.assertIn("medications", result)
        
        # Check that query was passed correctly
        self.assertEqual(result["query"], "ibuprofen")

class TestPubMedTools(unittest.TestCase):
    """Tests for PubMed article search tools."""
    
    def test_search_articles_structure(self):
        """Test that the search_articles function has the expected structure."""
        self.assertTrue(hasattr(pubmed, 'search_articles'))
        self.assertTrue(callable(pubmed.search_articles))
    
    def test_search_articles_results(self):
        """Test that search_articles returns results in the expected format."""
        # Run async function in a synchronous test
        result = asyncio.run(pubmed.search_articles("diabetes treatment", limit=2))
        
        # Check response structure
        self.assertIn("status", result)
        self.assertIn("message", result)
        self.assertIn("query", result)
        self.assertIn("articles", result)
        
        # Check that query was passed correctly
        self.assertEqual(result["query"], "diabetes treatment")

class TestClinicalTrialsTools(unittest.TestCase):
    """Tests for ClinicalTrials.gov search tools."""
    
    def test_search_trials_structure(self):
        """Test that the search_trials function has the expected structure."""
        self.assertTrue(hasattr(trials, 'search_trials'))
        self.assertTrue(callable(trials.search_trials))
    
    def test_search_trials_results(self):
        """Test that search_trials returns results in the expected format."""
        # Run async function in a synchronous test
        result = asyncio.run(trials.search_trials("cancer", limit=2))
        
        # Check response structure
        self.assertIn("status", result)
        self.assertIn("message", result)
        self.assertIn("condition", result)
        self.assertIn("trials", result)
        
        # Check that condition was passed correctly
        self.assertEqual(result["condition"], "cancer")

if __name__ == "__main__":
    unittest.main()
