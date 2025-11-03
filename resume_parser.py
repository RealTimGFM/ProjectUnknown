from __future__ import annotations
import os
from typing import Dict

from ats_parser import parse_file, adapt_for_backend

def parse_resume(filepath: str) -> Dict:
    """
    Entry point that supports both PDF and DOCX.
    For PDF: identical behavior as before (parse_file -> adapt_for_backend).
    For DOCX: extracts text via python-docx, then tries ats_parser text pipeline.
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".pdf":
        res = parse_file(filepath)
        return adapt_for_backend(res)

    if ext == ".docx":
        # 1) Extract text from DOCX
        try:
            from docx import Document
        except ImportError as e:
            raise RuntimeError(
                "python-docx is not installed. Run: pip install python-docx"
            ) from e

        doc = Document(filepath)
        text = "\n".join(p.text for p in doc.paragraphs).strip()

        try:
            from ats_parser import parse_text  # optional, only if exists
            res = parse_text(text)
            return adapt_for_backend(res)
        except Exception:
            # 3) Fallback: use sections/rules directly, then flatten into your dict shape
            #    This keeps things resilient if parse_text does not exist in your build.
            try:
                from ats_parser import sections, rules
            except Exception as inner_e:
                # If your repo doesn't expose sections/rules, surface the root cause
                raise RuntimeError(
                    "ats_parser text pipeline not available. "
                    "Expose parse_text() or sections/rules in ats_parser."
                ) from inner_e

            # --- very lightweight text → fields pass ---
            secs = sections.split_sections(text)
            contacts = rules.extract_contacts(text) or {}
            skills = rules.extract_skills(secs.get("SKILLS", "")) or ""
            education = rules.fallback_education(secs.get("EDUCATION", ""))
            experience = rules.fallback_experience(secs.get("EXPERIENCE", ""))
            languages = rules.extract_languages(secs.get("LANGUAGES", "")) if hasattr(rules, "extract_languages") else ""
            projects = rules.extract_projects(secs.get("PROJECTS", "")) if hasattr(rules, "extract_projects") else ""

            return {
                "raw_text": text,
                "name": contacts.get("name", ""),
                "first_name": contacts.get("first_name", ""),
                "middle_name": contacts.get("middle_name", ""),
                "last_name": contacts.get("last_name", ""),
                "phone": contacts.get("phone", ""),
                "email": contacts.get("email", ""),
                "links": contacts.get("links", []),
                "skills": skills,
                "education": education,
                "experience": experience,
                "languages": languages,
                "projects": projects,
            }
    raise ValueError(f"Unsupported file type: {ext}")
