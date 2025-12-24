from ats_parser import rules


def test_projects_tech_stack_must_be_allowlist_only():
    lines = [
        "PROJECTS",
        "StockAI — Personal Project (2024-01 to Present)",
        "Tech: Python, Pandas, NumPy, FooBarTech, BazQuxFramework",
        "Link: https://github.com/example/stockai",
    ]
    projects = rules.extract_projects(lines)
    assert projects and isinstance(projects, list)
    tech = projects[0].get("tech_stack") or []
    # allowlisted
    assert "Python" in tech
    # not allowlisted
    assert "FooBarTech" not in tech
    assert "BazQuxFramework" not in tech
