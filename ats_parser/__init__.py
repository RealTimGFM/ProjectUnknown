"""Hybrid resume parser package (rules + optional LLM)."""

from . import rules
from .parser import parse_file, parse_bytes, adapt_for_backend

__all__ = ["rules", "parse_file", "parse_bytes", "adapt_for_backend"]
