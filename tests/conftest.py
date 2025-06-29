"""
Pytest configuration and shared fixtures for DailyMed tests.
"""

import pytest
from app.utils.dailymed import DailyMedClient

@pytest.fixture(scope="session")
def client():
    """Return a shared DailyMedClient instance for all tests."""
    return DailyMedClient()
