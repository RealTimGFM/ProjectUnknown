import pytest
from ats_parser.sections import split_sections


def test_split_sections_basic_headings_routed():
    text = """
Summary
I build backend systems.

Skills:
Python, SQL

Experience
2020 - 2021
Developer at Example Inc

Education
BSc - Computer Science
LaSalle College, Montreal, QC
"""
    secs = split_sections(text)
    assert "SUMMARY" in secs and secs["SUMMARY"]
    assert "SKILLS" in secs and secs["SKILLS"]
    assert "EXPERIENCE" in secs and secs["EXPERIENCE"]
    assert "EDUCATION" in secs and secs["EDUCATION"]


@pytest.mark.xfail(reason="Projects currently route into EXPERIENCE because EXPERIENCE regex includes projects?. Must be separated.")
def test_projects_heading_must_route_to_projects_not_experience():
    text = """
Projects
StockAI — Python, Pandas — 2024
- Built backtesting engine

Experience
2021 - 2023
Developer at Example Inc
"""
    secs = split_sections(text)
    assert secs["PROJECTS"], "Projects section must not be empty"
    assert not any("StockAI" in ln for ln in secs["EXPERIENCE"]), "Project lines must not appear in EXPERIENCE"


@pytest.mark.xfail(reason="Projects heading aliases not complete yet (Academic/Side/Selected/Key).")
@pytest.mark.parametrize(
    "heading",
    ["Projects", "Selected Projects", "Personal Projects", "Academic Projects", "Side Projects", "Key Projects"],
)
def test_projects_heading_aliases_all_map_to_projects(heading):
    text = f"""
{heading}
MyCoolApp — Flask — 2024
- Did X
"""
    secs = split_sections(text)
    assert secs["PROJECTS"], f"{heading} should map to PROJECTS"
