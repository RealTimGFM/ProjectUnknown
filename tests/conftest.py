import sys
import types
import pytest


@pytest.fixture(autouse=True)
def _stub_heavy_pdf_libs():
    """
    Prevent import-time failures for ats_parser.ingest which imports fitz/pdfplumber.
    We never call real PDF parsing in unit tests; pipeline tests monkeypatch read_pdf_text.
    """
    if "fitz" not in sys.modules:
        sys.modules["fitz"] = types.SimpleNamespace(open=lambda *a, **k: None, Matrix=lambda *a, **k: None)
    if "pdfplumber" not in sys.modules:
        sys.modules["pdfplumber"] = types.SimpleNamespace(open=lambda *a, **k: None)
