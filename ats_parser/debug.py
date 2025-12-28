from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .parser import parse_text
from .sections import split_sections


def debug_parse_text(text: str) -> dict[str, Any]:
    """
    Debug helper to inspect what the parser extracted.

    NOTE:
    - ProjectItem fields are: title, role, tech_stack, links, dates, bullets
    - Contact fields are: name, email, phone, websites
    """
    resume = parse_text(text)
    secs = split_sections(text)

    # show both uppercase + lowercase views, but keep original dict
    sections_out: dict[str, list[str]] = {}
    for k, v in (secs or {}).items():
        if isinstance(k, str) and isinstance(v, list):
            sections_out[k] = v

    # ----- EXPERIENCE SNAPSHOT -----
    exp_out = []
    for e in (resume.experience or []):
        bullets = list(getattr(e, "bullets", []) or [])
        tech = list(getattr(e, "technologies", []) or [])
        dates = getattr(e, "dates", None)

        exp_out.append(
            {
                "title": getattr(e, "title", "") or "",
                "company": getattr(e, "company", "") or "",
                "location": getattr(e, "location", "") or "",
                "start": getattr(dates, "start", "") if dates else "",
                "end": getattr(dates, "end", "") if dates else "",
                "months": getattr(dates, "months", 0) if dates else 0,
                "bullets_count": len(bullets),
                "bullets_preview": bullets[:3],
                "technologies_count": len(tech),
                "technologies_preview": tech[:10],
            }
        )

    # ----- PROJECTS SNAPSHOT -----
    projects = list(getattr(resume, "projects", []) or [])
    proj_out = []
    for p in projects:
        bullets = list(getattr(p, "bullets", []) or [])
        tech_stack = list(getattr(p, "tech_stack", []) or [])
        links = list(getattr(p, "links", []) or [])
        dates = getattr(p, "dates", None)

        # Backward-compatible fallbacks (in case older objects exist)
        title = getattr(p, "title", None) or getattr(p, "name", "") or ""
        tech_stack = tech_stack or list(getattr(p, "technologies", []) or [])
        links = links or list(getattr(p, "urls", []) or [])

        proj_out.append(
            {
                "title": title,
                "role": getattr(p, "role", "") or "",
                "start": getattr(dates, "start", "") if dates else "",
                "end": getattr(dates, "end", "") if dates else "",
                "tech_stack_count": len(tech_stack),
                "tech_stack_preview": tech_stack[:15],
                "links": links,
                "bullets_count": len(bullets),
                "bullets_preview": bullets[:3],
            }
        )

    # ----- EDUCATION SNAPSHOT -----
    education = list(getattr(resume, "education", []) or [])
    edu_out = []
    for ed in education:
        dates = getattr(ed, "dates", None)
        edu_out.append(
            {
                "degree": getattr(ed, "degree", "") or "",
                "field": getattr(ed, "field", "") or "",
                "school": getattr(ed, "school", "") or "",
                "location": getattr(ed, "location", "") or "",
                "start": getattr(dates, "start", "") if dates else "",
                "end": getattr(dates, "end", "") if dates else "",
            }
        )

    # ----- FLAGS -----
    flags_out: dict[str, Any] = {}
    flags = getattr(resume, "flags", None)
    if flags:
        if isinstance(flags, dict):
            flags_out = flags
        else:
            try:
                flags_out = asdict(flags)  # dataclass
            except Exception:
                flags_out = {"raw": str(flags)}

    # ----- CONTACT -----
    c = getattr(resume, "contact", None)
    websites = []
    if c:
        websites = getattr(c, "websites", None) or getattr(c, "links", None) or []
    contact_out = {
        "name": getattr(c, "name", "") if c else "",
        "email": getattr(c, "email", "") if c else "",
        "phone": getattr(c, "phone", "") if c else "",
        "websites": websites or [],
    }

    return {
        "sections": sections_out,
        "contact": contact_out,
        "counts": {
            "skills": len(getattr(resume, "skills", []) or []),
            "experience": len(resume.experience or []),
            "projects": len(projects),
            "education": len(education),
        },
        "skills_preview": (getattr(resume, "skills", []) or [])[:25],
        "experience": exp_out,
        "projects": proj_out,
        "education": edu_out,
        "flags": flags_out,
    }
