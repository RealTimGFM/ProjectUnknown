import pytest


def _get_projects_extractor():
    # Contract: implement one of these in ats_parser.rules
    import ats_parser.rules as rules
    if hasattr(rules, "extract_projects"):
        return rules.extract_projects
    if hasattr(rules, "fallback_projects"):
        return rules.fallback_projects
    return None


@pytest.mark.xfail(reason="Projects extraction not implemented yet (title, tech_stack, links, role, date_range).")
def test_projects_extraction_happy_path_structured_fields():
    fn = _get_projects_extractor()
    assert fn is not None, "Implement ats_parser.rules.extract_projects() or fallback_projects()"

    lines = [
        "StockAI — Quant Research Platform",
        "Role: Backend Developer",
        "Tech: Python, Pandas, SQL",
        "2024 – Present",
        "https://github.com/RealTimGFM/StockAI",
        "- Built backtesting pipeline",
    ]
    projects = fn(lines)

    assert isinstance(projects, list) and len(projects) >= 1
    p = projects[0]

    # Required fields per your requirement
    assert p.get("title")
    assert p.get("role")
    assert isinstance(p.get("tech_stack"), list)
    assert isinstance(p.get("links"), list)
    assert isinstance(p.get("dates"), dict)
    assert "start" in p["dates"] and "end" in p["dates"]


@pytest.mark.xfail(reason="Need disambiguation so job titles like 'Project Manager' stay in EXPERIENCE, not PROJECTS.")
def test_word_project_in_job_title_is_experience_not_project():
    # This is a contract test: future logic should ensure this never becomes a project.
    fn = _get_projects_extractor()
    assert fn is not None

    lines = [
        "Project Manager at Example Inc",
        "2020 – 2021",
        "- Managed delivery",
    ]
    projects = fn(lines)
    assert projects == [], "Project Manager is EXPERIENCE, not a project"
