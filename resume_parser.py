# resume_parser.py
import re
import pdfplumber
from dateutil import parser as dateparser
from typing import List, Dict, Tuple

# === helpers ===
MONTHS = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*"
YEAR = r"(19|20)\d{2}"
DATE_RE = re.compile(
    rf"(?P<start>({MONTHS}\s+{YEAR}|{YEAR}))\s*[-–—]\s*(?P<end>({MONTHS}\s+{YEAR}|{YEAR}|Present|Current))",
    re.IGNORECASE,
)

TECH_SKILLS = {
    # add more as needed
    "python",
    "java",
    "c++",
    "c#",
    "javascript",
    "typescript",
    "html",
    "css",
    "sql",
    "nosql",
    "react",
    "node",
    "express",
    "django",
    "flask",
    "fastapi",
    "pandas",
    "numpy",
    "scikit-learn",
    "pytorch",
    "tensorflow",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "postgres",
    "mysql",
    "sqlite",
    "git",
    "linux",
    "bash",
}
SOFT_SKILLS = {
    "leadership",
    "communication",
    "teamwork",
    "problem solving",
    "adaptability",
    "mentoring",
    "ownership",
    "collaboration",
}

SECTION_ALIASES = {
    "SUMMARY": {"summary", "professional summary", "profile"},
    "EXPERIENCE": {
        "experience",
        "work experience",
        "employment",
        "employment history",
        "professional experience",
    },
    "EDUCATION": {"education", "academic background"},
    "PROJECTS": {"projects", "personal projects", "notable projects"},
    "SKILLS": {"skills", "technical skills"},
    "LANGUAGES": {"languages", "spoken languages"},
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _which_section(line: str) -> str | None:
    up = _norm(line).lower()
    for key, aliases in SECTION_ALIASES.items():
        if up in aliases:
            return key
    return None


def _read_pdf_text(path: str) -> str:
    text = ""
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            t = p.extract_text() or ""
            text += t + "\n"
    return text


def _split_sections(text: str) -> dict[str, List[str]]:
    sections: dict[str, List[str]] = {}
    current = None
    for raw in text.splitlines():
        line = _norm(raw)
        if not line:
            continue
        sec = _which_section(line)
        if sec:
            current = sec
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return sections


def _parse_date_range(s: str) -> Tuple[str | None, str | None, int | None]:
    m = DATE_RE.search(s)
    if not m:
        return None, None, None
    start_raw = m.group("start")
    end_raw = m.group("end")
    try:
        start_dt = dateparser.parse(
            start_raw, fuzzy=True, default=dateparser.parse("Jan 1 2000")
        )
    except Exception:
        start_dt = None
    end_dt = None
    if end_raw and re.search(r"present|current", end_raw, re.I) is None:
        try:
            end_dt = dateparser.parse(
                end_raw, fuzzy=True, default=dateparser.parse("Jan 1 2000")
            )
        except Exception:
            end_dt = None
    duration = None
    if start_dt and end_dt:
        duration = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month)
    return (start_raw if start_raw else None, end_raw if end_raw else None, duration)


def _extract_skills(text: str) -> Tuple[str, str]:
    low = text.lower()
    tech_found = sorted(
        {w for w in TECH_SKILLS if re.search(rf"\b{re.escape(w)}\b", low)}
    )
    soft_found = sorted(
        {w for w in SOFT_SKILLS if re.search(rf"\b{re.escape(w)}\b", low)}
    )
    return (", ".join(tech_found), ", ".join(soft_found))


# === education parsing ===
def _parse_education(lines: List[str]) -> List[Dict]:
    items: List[Dict] = []
    buf: List[str] = []

    def flush():
        if not buf:
            return
        block = " | ".join(buf)
        # degree/level
        m_deg = re.search(
            r"(High School Diploma|Diploma|Associate|Bachelor(?:'s)?|Master(?:'s)?|BSc|MSc|B\.?Eng|M\.?Eng|PhD|Doctorate)",
            block,
            re.I,
        )
        degree = m_deg.group(1) if m_deg else ""
        # field/major
        m_field = re.search(r"(in|of)\s+([A-Za-z &/+-]{2,})", block, re.I)
        field = _norm(m_field.group(2)) if m_field else ""
        # years
        start, end, _ = _parse_date_range(block)
        # school (best-effort: take first comma-separated chunk that isn’t degree/field)
        parts = [p.strip() for p in re.split(r"[|•\-–—]", block) if p.strip()]
        school = ""
        location = ""
        for p in parts:
            if degree and degree.lower() in p.lower():
                continue
            if field and field.lower() in p.lower():
                continue
            # likely "University of X, City"
            if re.search(r"(University|College|School|Institute)", p, re.I):
                school = p
                break
        # location heuristics
        m_loc = re.search(r"\b([A-Z][a-z]+(?:,?\s+[A-Z][a-z]+)+)\b", block)
        if m_loc:
            location = m_loc.group(1)
        items.append(
            {
                "level": _norm(degree),
                "field": _norm(field),
                "school_name": _norm(school),
                "location": _norm(location),
                "start_year": start,
                "end_year": end,
            }
        )
        buf.clear()

    for ln in lines:
        # a new education entry often starts with a degree or school name
        if (
            re.search(
                r"(University|College|School|Institute|BSc|MSc|Bachelor|Master|PhD|Diploma)",
                ln,
                re.I,
            )
            and buf
        ):
            flush()
        buf.append(ln)
    flush()
    return [e for e in items if any(e.values())]


# === experience parsing ===
def _parse_experience(lines: List[str]) -> List[Dict]:
    items: List[Dict] = []
    cur: Dict | None = None
    bullet_re = re.compile(r"^(\s*[-*•]\s+)")
    for ln in lines:
        # header line with date range
        if DATE_RE.search(ln):
            # start a new entry
            if cur:
                items.append(cur)
            start, end, dur = _parse_date_range(ln)
            # Try to split "Role — Company — Location"
            head = DATE_RE.split(ln)[0].strip(" -–—|")
            parts = [p.strip() for p in re.split(r"[|•\-–—]", head) if p.strip()]
            position = parts[0] if parts else ""
            company = parts[1] if len(parts) > 1 else ""
            location = parts[2] if len(parts) > 2 else ""
            cur = {
                "position": _norm(position),
                "company_name": _norm(company),
                "location": _norm(location),
                "start_date": start,
                "end_date": end,
                "duration_months": dur,
                "description": "",
                "skills_used_tech": [],
                "skills_used_soft": [],
            }
            continue

        # description/bullets
        if cur:
            line_clean = bullet_re.sub("", ln)
            cur["description"] = (
                cur["description"] + ("\n" if cur["description"] else "") + line_clean
            ).strip()
            # accumulate skills on the fly
            tech_csv, soft_csv = _extract_skills(line_clean)
            if tech_csv:
                cur["skills_used_tech"].extend(
                    [s.strip() for s in tech_csv.split(",") if s.strip()]
                )
            if soft_csv:
                cur["skills_used_soft"].extend(
                    [s.strip() for s in soft_csv.split(",") if s.strip()]
                )
        else:
            # a stray line before any header: skip
            pass

    if cur:
        # dedupe skills
        cur["skills_used_tech"] = sorted(list(set(cur["skills_used_tech"])))
        cur["skills_used_soft"] = sorted(list(set(cur["skills_used_soft"])))
        items.append(cur)

    # final dedupe for all entries
    for e in items:
        e["skills_used_tech"] = sorted(list(set(e.get("skills_used_tech", []))))
        e["skills_used_soft"] = sorted(list(set(e.get("skills_used_soft", []))))
    return items


# === project parsing (light) ===
def _parse_projects(lines: List[str]) -> List[Dict]:
    items: List[Dict] = []
    buf: List[str] = []

    def flush(title_guess=""):
        if not buf and not title_guess:
            return
        text = "\n".join(buf).strip()
        items.append(
            {
                "title": title_guess or (text.split("\n")[0][:80] if text else ""),
                "description": text,
            }
        )
        buf.clear()

    for ln in lines:
        if DATE_RE.search(ln) and buf:
            flush(title_guess=buf[0] if buf else "")
            buf = []
        buf.append(ln)
    flush(title_guess=buf[0] if buf else "")
    return items


# === public API ===
def parse_resume(filepath: str) -> Dict:
    text = _read_pdf_text(filepath)
    lines = [l for l in (text or "").splitlines()]

    # first non-empty line is often the name
    name = "Unknown"
    for l in lines:
        if _norm(l):
            name = _norm(l)
            break

    sections = _split_sections(text)
    education = _parse_education(sections.get("EDUCATION", []))
    experience = _parse_experience(sections.get("EXPERIENCE", []))
    projects = _parse_projects(sections.get("PROJECTS", []))

    # whole-document skills / languages (fallback)
    skills_tech_doc, skills_soft_doc = _extract_skills(text)
    langs_line = " ".join(sections.get("LANGUAGES", []))
    langs = (
        ", ".join([w.strip() for w in re.split(r"[•,;/|]", langs_line) if w.strip()])
        if langs_line
        else ""
    )

    # summary is everything between name and first section header
    summary_lines = []
    hit_first_section = False
    for l in lines:
        if _which_section(l):
            hit_first_section = True
            break
        if _norm(l) and _norm(l) != name:
            summary_lines.append(_norm(l))
    summary = (
        " ".join(summary_lines[:5])
        if not hit_first_section
        else " ".join(summary_lines)
    )

    # ensure required keys
    return {
        "name": name,
        "summary": summary,
        "education": education,  # list[dict]
        "experience": experience,  # list[dict] with skills_used_{tech,soft}
        "projects": projects,  # list[dict]
        "skills": skills_tech_doc,  # CSV (technical)
        "languages": langs,  # CSV
        "raw_text": text or "",
    }
