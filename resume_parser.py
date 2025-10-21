
from __future__ import annotations
# Drop-in replacement using ats_parser
from ats_parser import parse_file, adapt_for_backend

def parse_resume(filepath: str) -> dict:
    res = parse_file(filepath)
    return adapt_for_backend(res)
