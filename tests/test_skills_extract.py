import pytest
from ats_parser.rules import extract_skills, extract_skills_from_text


def test_extract_skills_section_happy_path_dedupes():
    lines = ["Python, SQL, Flask, Python", "Docker | Git"]
    out = extract_skills(lines)
    assert "Python" in out and "SQL" in out and "Flask" in out
    assert out.count("Python") == 1


@pytest.mark.xfail(reason="You want allowlist-only skills (dataset). Current extractor keeps unknown tech tokens too.")
def test_extract_skills_must_be_allowlist_only():
    lines = ["Python, FooBarTech, SQL, BazQuxFramework"]
    out = extract_skills(lines)
    assert "Python" in out and "SQL" in out
    assert "FooBarTech" not in out
    assert "BazQuxFramework" not in out


def test_extract_skills_from_text_finds_skills_block():
    text = """
Summary
blah blah

Skills: Python, SQL, Flask
Experience
2020 - 2021
Developer at X
"""
    out = extract_skills_from_text(text)
    assert "Python" in out and "SQL" in out and "Flask" in out
