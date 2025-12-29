from __future__ import annotations

import importlib
import os
import re
import unicodedata
from functools import lru_cache
from typing import Tuple

USE_OCR = os.getenv("USE_OCR", "0") == "1"
OCR_LANGS = os.getenv("OCR_LANGS", "en").split(",")
OCR_PAGE_LIMIT = int(os.getenv("OCR_PAGE_LIMIT", "3"))


def _norm_ws(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\ufeff", "")
    s = "".join(
        " " if (ch.isspace() or unicodedata.category(ch) == "Zs") else ch for ch in s
    )
    return re.sub(r"\s+", " ", s).strip()


@lru_cache(maxsize=1)
def _get_mupdf():
    """
    Return the real PyMuPDF module.
    Must NOT fail at import-time for the package; only fail when PDF parsing is requested.
    """
    for name in ("pymupdf", "fitz"):
        try:
            mod = importlib.import_module(name)
            if hasattr(mod, "open"):
                return mod
        except Exception:
            continue

    raise ImportError(
        "PyMuPDF is required for PDF parsing. If you installed the wrong 'fitz' package, run:\n"
        "  pip uninstall fitz -y\n"
        "  pip install PyMuPDF"
    )


def _get_pdfplumber():
    try:
        return importlib.import_module("pdfplumber")
    except Exception:
        return None


_ocr_reader = None


def _get_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        easyocr = importlib.import_module("easyocr")  # lazy
        _ocr_reader = easyocr.Reader(OCR_LANGS, gpu=False)
    return _ocr_reader


def _page_blocks_sorted(page):
    blocks = page.get_text("blocks") or []
    blocks.sort(key=lambda b: (round(b[1], 1), round(b[0], 1)))
    return blocks


def _blocks_to_text(blocks):
    lines = []
    for b in blocks:
        t = (b[4] or "").strip()
        if t:
            lines.append(t)
    return "\n".join(lines)


def _matrix_prerotate(mupdf, rotation_deg: int):
    mat = mupdf.Matrix(300 / 72, 300 / 72)
    rot = rotation_deg % 360

    # PyMuPDF API differences across versions
    if hasattr(mat, "preRotate"):
        return mat.preRotate(rot)
    if hasattr(mat, "prerotate"):
        return mat.prerotate(rot)

    return mat


def read_pdf_text(path: str) -> Tuple[str, int]:
    """
    Return (text, ocr_pages_used).
    Uses PyMuPDF blocks; falls back to page text; optional OCR; optional pdfplumber rescue.
    """
    mupdf = _get_mupdf()
    doc = mupdf.open(path)

    assembled = []
    ocr_count = 0

    for i, page in enumerate(doc):
        raw = _blocks_to_text(_page_blocks_sorted(page)) or (page.get_text("text") or "")

        if (
            USE_OCR
            and len(_norm_ws(raw)) < 120
            and ocr_count < OCR_PAGE_LIMIT
        ):
            mat = _matrix_prerotate(mupdf, int(getattr(page, "rotation", 0) or 0))
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
