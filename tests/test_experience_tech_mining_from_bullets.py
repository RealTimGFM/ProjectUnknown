import json
from ats_parser.rules import fallback_experience

def test_tech_mined_from_bullets(monkeypatch, tmp_path):
    compiled = tmp_path / "compiled"
    compiled.mkdir()

    (compiled / "tech_allowlist.txt").write_text(
        "C#\nSQL Server\nASP.NET\nDocker\n",
        encoding="utf-8",
    )
    (compiled / "tech_aliases.json").write_text(
        json.dumps({"c sharp": "C#", "asp net": "ASP.NET"}),
        encoding="utf-8",
    )

    monkeypatch.setenv("ATS_TECH_ALLOWLIST_DIR", str(compiled))

    text = "\n".join([
        "EXPERIENCE",
        "Jan 2025 – Present",
        "Back-end Developer (ASP.NET)",
        "Machine Builder Inc.",
        "Montreal, QC",
        "- Built APIs with ASP.NET using C# and SQL Server.",
        "- Did some nonsense work.",
    ])

    items = fallback_experience(text)
    assert items and items[0].get("technologies")

    tech = items[0]["technologies"]
    assert "ASP.NET" in tech
    assert "C#" in tech
    assert "SQL Server" in tech
    assert "nonsense" not in tech
