from __future__ import annotations
import importlib
from functools import lru_cache
from typing import Tuple
# Robust PyMuPDF import:
# Some environments accidentally install the PyPI package named "fitz" (NOT PyMuPDF),
# which can shadow PyMuPDF's expected API in some setups.
try:
    import fitz  # PyMuPDF typically exposes this name
except Exception:  # pragma: no cover
    fitz = None

if fitz is None or not hasattr(fitz, "open"):
    try:
        import pymupdf as fitz  # fallback for some versions
    except Exception:  # pragma: no cover
        fitz = None

if fitz is None or not hasattr(fitz, "open"):
    raise ImportError(
        "PyMuPDF is required. If you installed the wrong 'fitz' package, run:\n"
        "  pip uninstall fitz -y\n"
        "  pip install PyMuPDF"
    )

# keep the rest of your existing imports below (re, os, pdfplumber, etc.)

import os, re, unicodedata
from typing import Tuple
import fitz  # PyMuPDF
import pdfplumber

USE_OCR = os.getenv("USE_OCR", "0") == "1"
OCR_LANGS = (os.getenv("OCR_LANGS", "en").split(","))
@lru_cache(maxsize=1)
def _get_mupdf():
    # Prefer modern import path when available
    try:
        import pymupdf as mupdf  # type: ignore
        if hasattr(mupdf, "open") and hasattr(mupdf, "Document"):
            return mupdf
    except Exception:
        pass

    # Fallback: PyMuPDF commonly exposes as "fitz"
    try:
        import fitz as mupdf  # type: ignore
        if hasattr(mupdf, "open") and hasattr(mupdf, "Document"):
            return mupdf
    except Exception:
        pass

    return None


def _norm_ws(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\ufeff", "")
    s = "".join(" " if (ch.isspace() or unicodedata.category(ch) == "Zs") else ch for ch in s)
    return re.sub(r"\s+", " ", s).strip()

def _page_blocks_sorted(page):
    blocks = page.get_text("blocks") or []
    blocks.sort(key=lambda b: (round(b[1],1), round(b[0],1)))
    return blocks

def _blocks_to_text(blocks):
    lines = []
    for b in blocks:
        t = (b[4] or "").strip()
        if t:
            lines.append(t)
    return "\n".join(lines)

_ocr_reader = None
def _get_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr  # lazy
        _ocr_reader = easyocr.Reader(OCR_LANGS, gpu=False)
    return _ocr_reader

def read_pdf_text(path: str) -> Tuple[str, int]:
    """
    Returns: (extracted_text, ocr_pages_count)
    """
    mupdf = _get_mupdf()
    if mupdf is None:
        raise RuntimeError(
            "PyMuPDF not available. Install PyMuPDF (not the unrelated 'fitz' package)."
        )

    doc = mupdf.open(path)
    pages = []
    for page in doc:
        pages.append(page.get_text("text") or "")
    return "\n".join(pages), 0