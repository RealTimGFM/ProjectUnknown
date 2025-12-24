# tests/test_parser_pipeline_contract.py

def test_parse_file_returns_partial_results_with_warnings(monkeypatch):
    """
    Contract:
    parse_file() returns a Resume that:
    - has projects attached
    - has flags["warnings"] as list[str] (possibly empty)
    - still returns partial results even if some sections are weak
    """
    from ats_parser import parser as p

    sample_text = """
John Doe
john@example.com | (555) 123-4567

SUMMARY
Backend developer.

SKILLS
Python, Flask, PostgreSQL

EXPERIENCE
Software Engineer — Example Inc (2021-01 to Present)
- Built APIs.

PROJECTS
StockAI — Personal Project (2024-01 to Present)
- Built a backtesting platform.
Tech: Python, Pandas
Link: https://github.com/example/stockai
""".strip()

    # Avoid real PDF parsing in unit tests
    monkeypatch.setattr(p, "read_pdf_text", lambda _path: (sample_text, 0))

    res = p.parse_file("fake.pdf")

    # Pipeline contract
    assert hasattr(res, "projects")
    assert isinstance(res.flags.get("warnings"), list)
    assert len(res.projects) >= 1
