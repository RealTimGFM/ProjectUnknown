from pathlib import Path

from ats_parser.parser import parse_text


FIXTURE = Path(__file__).parent / "fixtures" / "quy_cv_en_sanitized.txt"


def test_regression_quy_cv_sanitized_thresholds():
    text = FIXTURE.read_text(encoding="utf-8")

    resume = parse_text(text)

    # 1) Contact
    assert resume.contact.email, "email should be extracted"
    assert resume.contact.phone, "phone should be extracted"

    # 2) Experience
    assert len(resume.experience) >= 2, "should extract at least 2 experience items"
    assert all(e.title for e in resume.experience[:2]), "titles should not be empty"
    assert any(e.bullets for e in resume.experience), "at least one experience should have bullets"

    # Company/location should show up for most entries on this fixture
    assert sum(1 for e in resume.experience if e.company) >= 2
    assert any(e.location for e in resume.experience)

    # 3) Skills
    assert len(resume.skills) >= 8, "skills should be non-empty (allowlist-filtered)"

    # 4) Present duration
    present_items = [e for e in resume.experience if getattr(e.dates, "end", None) == "Present"]
    assert present_items, "should detect at least one Present role"
    assert all(isinstance(e.dates.months, int) and e.dates.months >= 1 for e in present_items)
    
    # 5) Anti-bleed guard: bullets should not accidentally contain section headers
    bad_headers = {"EDUCATION", "PROJECTS", "SKILLS", "CERTIFICATIONS", "LANGUAGES", "SUMMARY"}
    for e in resume.experience:
        for b in e.bullets:
            assert b.strip().upper() not in bad_headers, f"bullet bleed detected: {b!r}"

