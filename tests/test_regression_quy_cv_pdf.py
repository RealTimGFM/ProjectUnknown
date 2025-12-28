from pathlib import Path
import os
import pytest

from ats_parser.parser import parse_file

pytestmark = pytest.mark.slow

def _find_pdf() -> Path | None:
    # Optional override: set QUY_CV_PDF to an absolute path on your machine
    override = os.environ.get("QUY_CV_PDF")
    if override:
        p = Path(override)
        if p.exists():
            return p

    candidates = [
        Path("uploads/1_QuyVuLuong_CV_EN.pdf"),
        Path("uploads/QuyVuLuong_CV_EN.pdf"),
        Path("tests/fixtures/QuyVuLuong_CV_EN.pdf"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

def test_regression_quy_cv_pdf_thresholds():
    pdf = _find_pdf()
    if not pdf:
        pytest.skip("QuyVuLuong_CV_EN.pdf not found (set QUY_CV_PDF or place it in uploads/).")

    try:
        r = parse_file(str(pdf))
    except ImportError:
        pytest.skip("PyMuPDF not available in this environment.")

    # Contact
    assert r.contact.email, "email should be extracted"
    assert r.contact.phone, "phone should be extracted"

    # Experience basics
    assert len(r.experience) >= 2, "should extract at least 2 experience items"
    assert all(e.title for e in r.experience[:2]), "titles should not be empty"

    # Company + location quality gates for this CV
    assert all(e.company for e in r.experience[:2]), "company should not be empty for first 2 items"
    assert all(e.location for e in r.experience[:2]), "location should not be empty for first 2 items"

    # Bullets should exist for at least one role
    assert any(len(e.bullets) >= 3 for e in r.experience), "expected some bullet content"

    # Skills should not be empty
    assert len(r.skills) >= 5, "skills should not be empty"
