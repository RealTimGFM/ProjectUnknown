"""PDF ingestion helpers (PyMuPDF + optional OCR/pdfplumber rescue)."""
from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Tuple


USE_OCR = os.getenv("ATS_USE_OCR", "0").lower() in ("1", "true", "yes", "on")
OCR_PAGE_LIMIT = int(os.getenv("ATS_OCR_PAGE_LIMIT", "0") or "0")


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


@lru_cache(maxsize=1)
def _fitz_status() -> str:
    """
    Returns:
      - "ok"      => fitz import works and has open()
      - "wrong"   => 'fitz' imports but does NOT have open() (wrong fitz package)
      - "missing" => import fitz failed
    """
    try:
        import fitz  # type: ignore
        return "ok" if hasattr(fitz, "open") else "wrong"
    except Exception:
        return "missing"


@lru_cache(maxsize=1)
def _get_mupdf():
    """
    Lazy-import PyMuPDF in a way that avoids crashing module import.
    We accept either:
      - import fitz (normal PyMuPDF)
      - import pymupdf as module (some setups)
    """
    try:
        import fitz  # type: ignore
        if hasattr(fitz, "open"):
            return fitz
    except Exception:
        pass

    try:
        import pymupdf  # type: ignore
        if hasattr(pymupdf, "open"):
            return pymupdf
    except Exception:
        pass

    return None


def _matrix_prerotate(mupdf, rotation: int):
    # Compatible across PyMuPDF versions
    mat = mupdf.Matrix(2, 2)
    try:
        return mat.prerotate(rotation)
    except Exception:
        try:
            return mat.preRotate(rotation)
        except Exception:
            return mat


def _page_blocks_sorted(page):
    """
    Return blocks sorted by top-to-bottom then left-to-right.
    page.get_text("blocks") typically returns:
      (x0, y0, x1, y1, text, block_no, block_type)
    """
    try:
        blocks = page.get_text("blocks") or []
    except Exception:
        return []

    # Sort by y0, then x0
    try:
        return sorted(blocks, key=lambda b: (b[1], b[0]))
    except Exception:
        return blocks


def _blocks_to_text(blocks) -> str:
    out = []
    for b in blocks or []:
        try:
            t = (b[4] or "").strip()
        except Exception:
            t = ""
        if t:
            out.append(t)
    return "\n".join(out).strip()


@lru_cache(maxsize=1)
def _get_pdfplumber():
    try:
        import pdfplumber  # type: ignore
        return pdfplumber
    except Exception:
        return None


@lru_cache(maxsize=1)
def _get_ocr():
    """
    Optional OCR via easyocr (only used when ATS_USE_OCR=1).
    Not installed by default; this keeps CI light.
    """
    import easyocr  # type: ignore
    return easyocr.Reader(["en"], gpu=False)


def read_pdf_text(path: str) -> Tuple[str, int]:
    """
    Return (text, ocr_pages_used).
    Uses PyMuPDF blocks; falls back to page text; optional OCR; optional pdfplumber rescue.
    """
    mupdf = _get_mupdf()
    if mupdf is None:
        if _fitz_status() == "wrong":
            raise ImportError(
                "Wrong 'fitz' module detected. Uninstall 'fitz' and install 'PyMuPDF':\n"
                "  pip uninstall fitz -y\n"
                "  pip install PyMuPDF\n"
            )
        raise ImportError(
            "PyMuPDF is required for PDF parsing. Install it with:\n"
            "  pip install PyMuPDF\n"
        )

    doc = mupdf.open(path)

    assembled = []
    ocr_count = 0

    for page in doc:
        raw = _blocks_to_text(_page_blocks_sorted(page)) or (page.get_text("text") or "")

        if USE_OCR and len(_norm_ws(raw)) < 120 and ocr_count < OCR_PAGE_LIMIT:
            rot = int(getattr(page, "rotation", 0) or 0)
            mat = _matrix_prerotate(mupdf, rot)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = pix.tobytes("png")
            reader = _get_ocr()
            lines = reader.readtext(img, detail=0, paragraph=True)
            raw = "\n".join(l.strip() for l in lines if l and l.strip())
            ocr_count += 1

        assembled.append(raw)

    doc.close()

    text = "\n".join(assembled).strip()

    # Optional rescue with pdfplumber if still sparse
    if len(_norm_ws(text)) < 120:
        pdfplumber = _get_pdfplumber()
        if pdfplumber is not None:
            try:
                with pdfplumber.open(path) as pdf:
                    text2 = "\n".join((p.extract_text() or "") for p in pdf.pages)
                if len(_norm_ws(text2)) > len(_norm_ws(text)):
                    text = text2
            except Exception:
                pass

    return (text or "") + "\n", ocr_count
