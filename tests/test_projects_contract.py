# tests/test_projects_contract.py

def test_projects_extraction_happy_path_structured_fields():
    """
    Contract:
    - rules.extract_projects(lines) returns list[dict]
    - each dict has: title, role, tech_stack(list[str]), links(list[str]), dates({start,end})
    """
    from ats_parser import rules

    sample_lines = [
        "PROJECTS",
        "StockAI — Personal Project (2024-01 to Present)",
        "Built a Python backtesting platform for equities/FX with walk-forward validation.",
        "Tech: Python, Pandas, NumPy, scikit-learn, PostgreSQL",
        "Link: https://github.com/example/stockai",
    ]

    projects = rules.extract_projects(sample_lines)
    assert isinstance(projects, list)
    assert len(projects) >= 1

    p0 = projects[0]
    assert p0.get("title")
    assert p0.get("role")
    assert isinstance(p0.get("tech_stack"), list)
    assert isinstance(p0.get("links"), list)
    assert isinstance(p0.get("dates"), dict)
    assert "start" in p0["dates"] and "end" in p0["dates"]


def test_word_project_in_job_title_is_experience_not_project():
    """
    Contract:
    - lines mentioning 'Project Manager' in EXPERIENCE should not be mis-read as a PROJECT.
    """
    from ats_parser import rules

    experience_lines = [
        "EXPERIENCE",
        "Project Manager — ABC Corp (2022-01 to 2023-06)",
        "Led delivery of internal systems and coordinated stakeholders.",
        "Tech: Jira, Confluence",
    ]

    projects = rules.extract_projects(experience_lines)
    assert projects == []
