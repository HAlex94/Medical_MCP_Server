#!/usr/bin/env python3
"""
FDA API v3 Module

The v3 FDA API provides 100% success rate drug label queries,
with optimized responses for LLM consumption.

This module includes:
- Direct generic name-based drug label searches
- Content optimization and token estimation for LLMs
- Support for compound drug names
- Comprehensive metadata
"""

from app.routes.fda.v3.routes import router
