# tests/conftest.py
import sys
import types

# Pytest imports conftest BEFORE importing test modules, so this prevents import-time crashes
# when ats_parser/__init__.py pulls in ats_parser/ingest.py (which imports fitz/pdfplumber).

def _stub_module(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)

_stub_module("fitz")        # PyMuPDF
_stub_module("pdfplumber")  # pdfplumber
