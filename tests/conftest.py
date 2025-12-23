# tests/conftest.py
import sys
import types

# Pytest loads conftest before importing test modules.
# This prevents import-time crashes if optional PDF libs are missing.

def _stub_module(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)

# ats_parser/ingest.py imports these at import-time in some environments
_stub_module("fitz")        # PyMuPDF (module name is fitz)
_stub_module("pdfplumber")  # pdfplumber
