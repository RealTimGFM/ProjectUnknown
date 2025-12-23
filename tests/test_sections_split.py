# tests/test_sections_split.py
import pytest
from ats_parser.sections import split_sections


def test_split_sections_has_projects_key():
    text = """
EXPERIENCE
- A

PROJECTS
- B
"""
    sections = split_sections(text)
    assert "projects" in sections


def test_projects_heading_must_route_to_projects_not_experience():
    text = """
PROJECTS
My App — Python, Flask
"""
    sections = split_sections(text)
    assert sections["projects"].strip() != ""
    assert sections["experience"].strip() == ""


@pytest.mark.parametrize(
    "heading",
    [
        "Projects",
        "Selected Projects",
        "Personal Projects",
        "Academic Projects",
        "Side Projects",
        "Key Projects",
    ],
)
def test_projects_heading_aliases_all_map_to_projects(heading):
    text = f"""
{heading}
My App — Python, Flask
"""
    sections = split_sections(text)
    assert sections["projects"].strip() != ""
    assert sections["experience"].strip() == ""


def test_experience_heading_goes_to_experience():
    text = """
EXPERIENCE
Software Developer at Example Inc
"""
    sections = split_sections(text)
    assert sections["experience"].strip() != ""
