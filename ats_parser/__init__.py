"""Hybrid resume parser package (rules + optional LLM)."""
from __future__ import annotations

from . import rules

__all__ = ["rules", "parse_file", "parse_bytes", "adapt_for_backend"]


def parse_file(path: str):
    from .parser import parse_file as _parse_file
    return _parse_file(path)


def parse_bytes(data: bytes):
    from .parser import parse_bytes as _parse_bytes
    return _parse_bytes(data)


def adapt_for_backend(resume):
    from .parser import adapt_for_backend as _adapt_for_backend
    return _adapt_for_backend(resume)
