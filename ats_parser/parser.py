from __future__ import annotations

from typing import List
import os
import tempfile

from .models import (
    Resume,
    Contact,
    ExperienceItem,
    EducationItem,
    DateSpan,
    ProjectItem,
)
from .ingest import read_pdf_text
from .sections import split_sections
from . import rules
from .llm import extract_experience_llm, extract_education_llm
from .reconcile import merge_experience


def _split_name(full: str):
    s = (full or "").strip()
    if not s:
        return "", "", ""
    parts = s.split()
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return parts[0], " ".join(parts[1:-1]), parts[-1]


def parse_file(path: str) -> Resume:
    text, ocr_pages = read_pdf_text(path)
    secs = split_sections(text)

    warnings: list[str] = []

    # ----- PROJECTS -----
    projects_lines = secs.get("PROJECTS") or []
    try:
        projects_raw = rules.extract_projects(projects_lines)
        projects = [ProjectItem(**p) for p in (projects_raw or [])]
    except Exception as e:
        projects = []
        warnings.append(f"Projects extraction failed: {type(e).__name__}")

    if projects_lines and not projects:
        warnings.append("Projects section present but no projects were extracted.")

    # ----- CONTACTS + SKILLS -----
    contacts = rules.extract_contacts(text)

    skills_list = rules.extract_skills(secs.get("SKILLS", []))
    if not skills_list:
        # fallback if the splitter missed the section heading
        skills_list = rules.extract_skills_from_text(text)

    # ----- EXPERIENCE (RULES) -----
    exp_text = "\n".join(secs.get("EXPERIENCE") or [])
    exp_rule_source = exp_text or text

    exp_rule = [
        ExperienceItem(
            title=it["title"],
            company=it["company"],
            location=it["location"],
            dates=DateSpan(**it["dates"]),
            bullets=it["bullets"],
            technologies=it["technologies"],
            confidence=it.get("confidence", 0.55),
        )
        for it in rules.fallback_experience(exp_rule_source)
    ]

    if not exp_rule:
        # last resort: run fallback on whole doc
        exp_rule = [
            ExperienceItem(
                title=it["title"],
                company=it["company"],
                location=it["location"],
                dates=DateSpan(**it["dates"]),
                bullets=it["bullets"],
                technologies=it["technologies"],
                confidence=it.get("confidence", 0.55),
            )
            for it in rules.fallback_experience(text)
        ]

    # ----- EDUCATION -----
    edu_lines = secs.get("EDUCATION") or []
    edu_rule = [
        EducationItem(
            degree=it["degree"],
            field=it["field"],
            school=it["school"],
            location=it["location"],
            dates=DateSpan(**it["dates"]),
            gpa=it.get("gpa"),
        )
        for it in (rules.fallback_education(edu_lines) if edu_lines else [])
    ]

    # LLM extraction (best-effort)
    try:
        edu_llm: List[EducationItem] = extract_education_llm("\n".join(edu_lines)) or []
    except Exception as e:
        edu_llm = []
        warnings.append(f"Education LLM failed: {type(e).__name__}")

    # Prefer deterministic rules; fall back to LLM only if rules found nothing
    education = edu_rule or edu_llm

    # ----- EXPERIENCE (LLM) + MERGE -----
    try:
        exp_llm: List[ExperienceItem] = extract_experience_llm(exp_text) or []
    except Exception as e:
        exp_llm = []
        warnings.append(f"Experience LLM failed: {type(e).__name__}")

    experience = merge_experience(exp_rule, exp_llm)

    # ----- FLAGS -----
    # Only count uppercase buckets (the splitter also returns lowercase string views)
    sections_found = {}
    for k, v in secs.items():
        if isinstance(k, str) and k.isupper() and isinstance(v, list):
            sections_found[k] = len(v or [])

    flags = {
        "used_ocr": bool(ocr_pages),
        "sections_found": sections_found,
        "warnings": warnings,
    }

    resume = Resume(
        contact=Contact(
            name=contacts.get("name", ""),
            email=contacts.get("email") or None,
            phone=contacts.get("phone") or None,
            websites=contacts.get("links") or [],
        ),
        summary=" ".join((secs.get("SUMMARY", []) or [])[:5]),
        skills=skills_list,
        experience=experience,
        education=education,
        projects=projects,
        certifications=[],
        languages=[],
        raw_text=text,
        flags=flags,
    )
    return resume


def parse_bytes(data: bytes) -> Resume:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(data)
        tmp.flush()
        path = tmp.name
    try:
        return parse_file(path)
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


def adapt_for_backend(resume: Resume) -> dict:
    name = resume.contact.name or ""
    first, middle, last = _split_name(name)

    # Flatten experience for your UI
    exp_flat = []
    for e in resume.experience:
        exp_flat.append(
            {
                "position": e.title or "",
                "company_name": e.company or "",
                "location": e.location or "",
                "start_date": (e.dates.start or ""),
                "end_date": (e.dates.end or ""),
                "duration_months": e.dates.months,
                "description": "\n".join(e.bullets).strip(),
            }
        )

    # Flatten education
    edu_flat = []
    for ed in resume.education:
        sy = (ed.dates.start or "")[:4] if (ed.dates and ed.dates.start) else ""
        if ed.dates and ed.dates.end == "Present":
            ey = "Present"
        else:
            ey = (ed.dates.end or "")[:4] if (ed.dates and ed.dates.end) else ""
        edu_flat.append(
            {
                "level": ed.degree or "",
                "field": ed.field or "",
                "school_name": ed.school or "",
                "location": ed.location or "",
                "start_year": sy,
                "end_year": ey,
            }
        )

    # Flatten projects (for later UI)
    proj_flat = []
    for p in getattr(resume, "projects", []) or []:
        proj_flat.append(
            {
                "title": p.title or "",
                "role": p.role or "",
                "start_date": (p.dates.start or "") if p.dates else "",
                "end_date": (p.dates.end or "") if p.dates else "",
                "tech_stack": ", ".join(p.tech_stack or []),
                "links": [str(u) for u in (p.links or [])],
                "description": "\n".join(p.bullets or []).strip(),
            }
        )

    warnings_list = []
    try:
        warnings_list = (resume.flags or {}).get("warnings", []) or []
    except Exception:
        warnings_list = []

    return {
        "name": name,
        "first_name": first,
        "middle_name": middle,
        "last_name": last,
        "phone": resume.contact.phone or "",
        "email": str(resume.contact.email) if resume.contact.email else "",
        "links": [str(u) for u in (resume.contact.websites or [])],
        "education": edu_flat,
        "experience": exp_flat,
        "projects": proj_flat,
        "skills": ", ".join(resume.skills),
        "languages": ", ".join(resume.languages),
        "raw_text": resume.raw_text,
        "warnings": warnings_list,
    }
