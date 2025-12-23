import pytest


@pytest.mark.xfail(reason="Pipeline must add projects + warnings. Resume model currently has no projects and no warnings contract.")
def test_parse_file_returns_partial_results_with_warnings(monkeypatch):
    # Import after conftest stubs heavy libs
    from ats_parser import parser as p

    # Mock PDF ingest
    sample_text = """
Tim Nguyen
tim@example.com

Academic Projects
StockAI — Python — 2024 — https://github.com/x
Role: Backend Developer
Tech: Python, Pandas

Experience
2020 – 2021
Software Developer at Example Inc
- Built APIs
"""

    monkeypatch.setattr(p, "read_pdf_text", lambda path: (sample_text, 0))

    res = p.parse_file("dummy.pdf")

    # Contract: warnings exist (B)
    warnings = res.flags.get("warnings")
    assert isinstance(warnings, list)

    # Contract: projects separate from experience
    assert hasattr(res, "projects")
    assert res.projects, "Projects should be extracted"
    assert res.experience, "Experience should be extracted"
