import re


def split_sections(text: str) -> dict[str, list[str]]:
    SECTION_PATTERNS = {
        "SUMMARY": re.compile(
            r"^(summary|professional summary|profile)\b[:\-–—]?", re.I
        ),
        "EXPERIENCE": re.compile(
            r"^(experience|work (?:history|experience)|employment|professional experience|projects?)\b[:\-–—]?",
            re.I,
        ),
        "EDUCATION": re.compile(
            r"^(education|academic background|studies)\b[:\-–—]?", re.I
        ),
        "SKILLS": re.compile(
            r"^(skills|technical skills|technologies|tooling|competenc(?:y|ies))\b[:\-–—]?",
            re.I,
        ),
        "CERTS": re.compile(r"^(certifications?|licenses?)\b[:\-–—]?", re.I),
        "LANGUAGES": re.compile(r"^(languages?)\b[:\-–—]?", re.I),
        "PROJECTS": re.compile(
            r"^(projects|selected projects|personal projects)\b[:\-–—]?", re.I
        ),
    }
    lines = [l.rstrip() for l in text.splitlines()]
    cur = None
    out = {k: [] for k in SECTION_PATTERNS.keys()}
    out.setdefault("OTHER", [])
    for ln in lines:
        s = re.sub(r"\s+", " ", (ln or "").strip())
        if not s:
            continue
        switched = False
        for key, rx in SECTION_PATTERNS.items():
            if rx.match(s):
                cur = key
                switched = True
                break
        if not switched:
            (out[cur] if cur else out["OTHER"]).append(s)
    return out
