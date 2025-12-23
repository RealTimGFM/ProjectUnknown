import pytest


def test_parse_resume_pdf_calls_parse_file_and_adapt(monkeypatch, tmp_path):
    import resume_parser

    calls = {"parse_file": 0, "adapt": 0}

    class DummyResume:
        flags = {}
        raw_text = ""

    def fake_parse_file(path):
        calls["parse_file"] += 1
        return DummyResume()

    def fake_adapt(res):
        calls["adapt"] += 1
        return {"ok": True}

    monkeypatch.setattr(resume_parser, "parse_file", fake_parse_file)
    monkeypatch.setattr(resume_parser, "adapt_for_backend", fake_adapt)

    f = tmp_path / "x.pdf"
    f.write_bytes(b"%PDF-1.4 fake")

    out = resume_parser.parse_resume(str(f))
    assert out == {"ok": True}
    assert calls["parse_file"] == 1
    assert calls["adapt"] == 1


def test_parse_resume_unsupported_extension_raises(tmp_path):
    import resume_parser

    f = tmp_path / "x.txt"
    f.write_text("no")
    with pytest.raises(ValueError):
        resume_parser.parse_resume(str(f))
