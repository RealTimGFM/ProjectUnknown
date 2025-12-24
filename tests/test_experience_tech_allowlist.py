from ats_parser.rules import fallback_experience


def test_experience_technologies_must_be_allowlist_only():
    text = """
2020 - 2021
Software Developer at Example Inc
Tech: Python, SQL, FooBarTech
- Built APIs
"""
    items = fallback_experience(text)
    assert len(items) >= 1
    tech = items[0].get("technologies") or []
    assert "Python" in tech
    assert "SQL" in tech
    assert "FooBarTech" not in tech
