
from __future__ import annotations
import os, re, unicodedata
from typing import Tuple
import fitz  # PyMuPDF
import pdfplumber

USE_OCR = os.getenv("USE_OCR", "0") == "1"
OCR_LANGS = (os.getenv("OCR_LANGS", "en").split(","))

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
    """Return (text, ocr_pages_used). Uses blocks; falls back to text/ocr/pdfplumber."""
    doc = fitz.open(path)
    assembled, ocr_count = [], 0
    for i, page in enumerate(doc):
        raw = _blocks_to_text(_page_blocks_sorted(page)) or (page.get_text("text") or "")
        if len(_norm_ws(raw)) < 120 and USE_OCR:
            # high-res pix + OCR
            mat = fitz.Matrix(300/72, 300/72).preRotate((page.rotation or 0)%360)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = pix.tobytes("png")
            reader = _get_ocr()
            lines = reader.readtext(img, detail=0, paragraph=True)
            raw = "\n".join(l.strip() for l in lines if l and l.strip())
            ocr_count += 1
        assembled.append(raw)
    doc.close()
    text = "\n".join(assembled).strip()

    # rescue with pdfplumber if still sparse
    if len(_norm_ws(text)) < 120:
        try:
            with pdfplumber.open(path) as pdf:
                text2 = "\n".join((p.extract_text() or "") for p in pdf.pages)
            if len(_norm_ws(text2)) > len(_norm_ws(text)):
                text = text2
        except Exception:
            pass

    return (text or "") + "\n", ocr_count
