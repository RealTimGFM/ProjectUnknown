# tests/test_smoke.py
import importlib
import sys
import types

import pytest
from pathlib import Path

# Ensure project root is importable (so `import backend` works)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _import_fresh(module_name: str):
    """Import a module after removing it from sys.modules (so env vars apply)."""
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


def _install_dummy_ats_parser():
    """
    Provide a tiny in-memory ats_parser so tests don't need the real heavy parser stack.
    resume_parser imports: parse_file, adapt_for_backend.
    """
    dummy = types.ModuleType("ats_parser")
    calls = {"parse_file": 0, "adapt_for_backend": 0}

    def parse_file(path: str):
        calls["parse_file"] += 1
        # Minimal shape; resume_parser will pass this into adapt_for_backend()
        return {"raw_text": "hello from pdf", "skills": ["Python"]}

    def adapt_for_backend(res: dict):
        calls["adapt_for_backend"] += 1
        # Match the backend's expected keys (safe defaults)
        return {
            "raw_text": res.get("raw_text", ""),
            "name": "Test User",
            "first_name": "Test",
            "middle_name": "",
            "last_name": "User",
            "phone": "",
            "email": "",
            "links": [],
            "skills": res.get("skills", ""),
            "education": [],
            "experience": [],
            "languages": "",
            "projects": "",
        }

    dummy.parse_file = parse_file
    dummy.adapt_for_backend = adapt_for_backend
    sys.modules["ats_parser"] = dummy
    return calls


def test_parse_resume_pdf_calls_parse_pipeline(tmp_path):
    calls = _install_dummy_ats_parser()

    resume_parser = _import_fresh("resume_parser")

    out = resume_parser.parse_resume(str(tmp_path / "x.pdf"))

    assert calls["parse_file"] == 1
    assert calls["adapt_for_backend"] == 1
    assert out["raw_text"] == "hello from pdf"
    assert out["name"] == "Test User"


def test_parse_resume_unsupported_extension_raises():
    _install_dummy_ats_parser()
    resume_parser = _import_fresh("resume_parser")

    with pytest.raises(ValueError):
        resume_parser.parse_resume("x.txt")


def test_backend_allowed_file_and_init_db(tmp_path, monkeypatch):
    # Make backend use temp paths; backend runs init_db() at import time.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))

    _install_dummy_ats_parser()

    backend = _import_fresh("backend")

    assert backend.allowed_file("resume.pdf") is True
    assert backend.allowed_file("resume.docx") is True
    assert backend.allowed_file("resume.exe") is False

    # backend.init_db() is called at module import, so DB should exist.
    assert (tmp_path / "test.db").exists()
