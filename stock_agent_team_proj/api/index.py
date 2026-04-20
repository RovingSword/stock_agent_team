"""
Vercel Python Function entrypoint.

This file makes the FastAPI app available as a single Vercel Function.
"""

from web.app import app  # noqa: F401

