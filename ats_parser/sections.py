# ats_parser/sections.py
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Any

# Canonical (UPPERCASE) buckets used by the parser code
SECTION_PATTERNS: Tuple[Tuple[str, re.Pattern], ...] = (
    (
        "SUMMARY",
        re.compile(
            r"(?i)^(summary|profile|professional\s+summary|about\s+me|objective)\b"
        ),
    ),
    (
        "SKILLS",
        re.compile(r"(?i)^(skills|technical\s+skills|core\s+skills|key\s+skills)\b"),
    ),
    (
        "EXPERIENCE",
        # IMPORTANT: do NOT include "projects" here
        re.compile(
            r"(?i)^(work\s+experience|professional\s+experience|experience|employment|employment\s+history|career\s+history|industry\s+experience|relevant\s+experience)\b"
        ),
    ),
    (
        "PROJECTS",
        re.compile(
            r"(?i)^(projects|selected\s+projects|personal\s+projects|academic\s+projects|side\s+projects|key\s+projects)\b"
        ),
    ),
    (
        "EDUCATION",
        re.compile(r"(?i)^(education|academic\s+background|academics)\b"),
    ),
    (
        "CERTS",
        re.compile(r"(?i)^(certifications|certificates|certs|licenses)\b"),
    ),
    (
        "LANGUAGES",
        re.compile(r"(?i)^(languages|language)\b"),
    ),
)

# Lowercase aliases required by tests / external callers
LOWER_MAP: Dict[str, str] = {
    "SUMMARY": "summary",
    "SKILLS": "skills",
    "EXPERIENCE": "experience",
    "PROJECTS": "projects",
    "EDUCATION": "education",
    "CERTS": "certs",
    "LANGUAGES": "languages",
    "OTHER": "other",
}


def _match_heading(line: str, pat: re.Pattern) -> Optional[str]:
    """
    A line is a heading only if:
      - it matches at the beginning, AND
      - the rest of the line is empty OR starts with a delimiter (: - – —).
    Returns "tail text" after delimiter (e.g., 'Skills: Python, SQL' -> 'Python, SQL'),
    or "" if no tail, or None if not a heading.
    """
    m = pat.match(line)
    if not m:
        return None

    rest = line[m.end() :]
    if rest:
        # must be delimiter-only after heading
        if not re.match(r"^\s*[:\-–—]\s*", rest):
            return None
        rest = re.sub(r"^\s*[:\-–—]\s*", "", rest)

    return rest.strip()


def split_sections(text: str) -> Dict[str, Any]:
    """
    Splits resume text into sections by headings.

    Returns a dict that contains:
      - UPPERCASE keys -> list[str] (legacy / parser-friendly)
      - lowercase keys -> str (test-friendly: supports .strip())
    """
    buckets: Dict[str, List[str]] = {k: [] for k, _ in SECTION_PATTERNS}
    buckets["OTHER"] = []

    current = "OTHER"

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        switched = False
        for key, pat in SECTION_PATTERNS:
            tail = _match_heading(line, pat)
            if tail is None:
                continue

            current = key
            switched = True
            if tail:
                buckets[current].append(tail)
            break

        if switched:
            continue

        buckets[current].append(line)

    out: Dict[str, Any] = dict(buckets)

    # Add lowercase string views (what your tests expect)
    for upper, lower in LOWER_MAP.items():
        out[lower] = "\n".join(buckets.get(upper, [])).strip()

    return out
