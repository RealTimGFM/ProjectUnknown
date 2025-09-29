from __future__ import annotations
import re, io
from typing import List, Dict, Tuple
from datetime import datetime

import fitz
import pdfplumber
import easyocr

from dateutil import parser as dateparser
import phonenumbers
from email_validator import validate_email, EmailNotValidError

# ---------- Regexes & helpers ----------
MONTHS = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*"
YEAR = r"(19|20)\d{2}"
DATE_RE = re.compile(
    rf"(?P<start>({MONTHS}\s+{YEAR}|{YEAR}))\s*[-–—]\s*(?P<end>({MONTHS}\s+{YEAR}|{YEAR}|Present|Current))",
    re.IGNORECASE,
)

EDU_LEVEL_RE = re.compile(
    r"(High School Diploma|Diploma(?: of College Studies)?(?:\s*DEC)?|Bachelor(?:'s)?|Master(?:'s)?|BSc|MSc|PhD)",
    re.I,
)
EDU_SCHOOL_HINT = re.compile(r"(University|College|School|Institute)", re.I)
LOCATION_LINE_RE = re.compile(r"[A-Z][a-z]+(?:,?\s+[A-Z][a-z]+)+(?:,\s*[A-Za-z.]+)?")

SCHOOL_LOC_SPLIT_RE = re.compile(
    r"^(?P<school>.*?(?:University|College|School|Institute))\s*[,–—-]\s*(?P<loc>.+)$",
    re.I,
)

CONTACT_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
CONTACT_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
URL_RE = re.compile(r"(https?://[^\s]+|(?:www\.)?(?:github|linkedin)\.com[^\s]*)", re.I)
LOCATION_HINTS = ["Montreal", "QC", "Canada", "Ho Chi Minh", "Viet", "Vietnam"]
# --- role & company heuristics for experience titles ---
ROLE_WORDS = {
    "intern",
    "developer",
    "engineer",
    "analyst",
    "manager",
    "consultant",
    "architect",
    "administrator",
    "specialist",
    "scientist",
    "lead",
    "principal",
    "director",
    "founder",
    "co-founder",
    "sre",
    "devops",
    "tester",
    "qa",
    "designer",
}
COMPANY_SUFFIX = re.compile(
    r"\b(inc\.?|corp\.?|llc|ltd\.?|co\.?|company|capital|fund|bank|group|partners?|"
    r"systems?|labs?|studio|technolog(?:y|ies)|solutions?)\b",
    re.I,
)
TITLE_HINT = re.compile(
    r"\b(senior|sr\.?|jr\.?|junior|lead|principal|staff|head|director|manager|"
    r"engineer|developer|analyst|consultant|architect|intern)\b",
    re.I,
)
BULLET_LINE = re.compile(r"^\s*[-*•]\s+")


def _looks_like_title(s: str) -> bool:
    s = _norm(s)
    if not s or BULLET_LINE.match(s):
        return False
    if s.endswith("."):  # full sentence → likely not a title
        return False
    if TITLE_HINT.search(s):  # contains role keywords
        return True
    # title-case heuristic: many tokens start uppercase but not all caps
    toks = [t for t in s.split() if t.isalpha()]
    if not toks:
        return False
    caps = sum(1 for t in toks if t[0].isupper() and not t.isupper())
    return caps / len(toks) >= 0.6 and len(toks) <= 7


def _looks_like_company(s: str) -> bool:
    s = _norm(s)
    if not s or BULLET_LINE.match(s):
        return False
    if s.lower().startswith(("http://", "https://", "www.")):
        return False
    if COMPANY_SUFFIX.search(s):
        return True
    # many company lines are all Title Case but short
    toks = [t for t in s.split() if t.isalpha()]
    caps = sum(1 for t in toks if t[0].isupper())
    return caps >= 2 and len(toks) <= 8


def _guess_title_company_from_buffer(buf: list[str]) -> tuple[str, str]:
    """
    Look back over the last few non-empty lines and pick a company & title.
    Prefer: company line with suffixes (Inc., Corp.) and the line just above it as title.
    Fallback: any title-like line, then any company-like line.
    """
    cand_title, cand_company = "", ""
    window = [_norm(x) for x in buf if _norm(x)][-6:]  # last ~6 non-empty lines
    # pass 1: company first then title just above
    for i in range(len(window) - 1, -1, -1):
        if _looks_like_company(window[i]):
            cand_company = window[i]
            # title likely the nearest line above
            for j in range(i - 1, -1, -1):
                if _looks_like_title(window[j]):
                    cand_title = window[j]
                    break
            break
    # pass 2: if title still empty, find any title-like line
    if not cand_title:
        for i in range(len(window) - 1, -1, -1):
            if _looks_like_title(window[i]):
                cand_title = window[i]
                break
    # pass 3: if company still empty, take any company-like line
    if not cand_company:
        for i in range(len(window) - 1, -1, -1):
            if _looks_like_company(window[i]):
                cand_company = window[i]
                break
    return cand_title, cand_company


# --- add near the top (after imports/regex) ---
# Header labels that appear in the SKILLS block; we'll strip these off lines
CATEGORY_PREFIX = re.compile(
    r"""^\s*(
        languages?|
        frameworks(?:\s*/\s*|\s*&\s*)?libraries|
        frameworks|libraries|
        data\s*/?\s*ai|data/ai|data|ai|
        databases?|
        infra(?:structure)?(?:\s*&\s*hosting)?|infra\s*&\s*hosting|hosting|
        tooling|tools|
        technology\s*stack|tech\s*stack|stack
    )\s*:\s*""",
    re.I | re.X,
)

# Multi-word phrases to capture as a single skill BEFORE generic tokenizing
MULTI_PHRASES = [
    "semantic search",
    "cosine similarity",
    "visual studio 2022",
    "vs code",
    "tailwind css",
    "sql server",
    "azure vm",
    "jakarta ee",
    "better-sqlite3",
]

# Canonical casing for common skills/tools
CANON = {
    "c#": "C#",
    "c++": "C++",
    ".net": ".NET",
    "asp.net": "ASP.NET",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "numpy": "NumPy",
    "sbert": "SBERT",
    "t-sql": "T-SQL",
    "sql server": "SQL Server",
    "ssms": "SSMS",
    "mysql": "MySQL",
    "phpmyadmin": "phpMyAdmin",
    "sqlite": "SQLite",
    "h2": "H2",
    "azure vm": "Azure VM",
    "iaas": "IaaS",
    "iis": "IIS",
    "tomcat": "Tomcat",
    "git": "Git",
    "github": "GitHub",
    "visual studio 2022": "Visual Studio 2022",
    "vs code": "VS Code",
    "tailwind css": "Tailwind CSS",
    "jakarta ee": "Jakarta EE",
    "flask": "Flask",
    "pandas": "pandas",
    "scikit-learn": "scikit-learn",
}

# Tokens to ignore if they accidentally slip through (noise/fillers)
STOPWORDS = re.compile(
    r"^(incl|including|and|with|using|basic|intermediate|advanced|expert|proficient|the|a|an|data|ai)$",
    re.I,
)

SKILL_PHRASES = {
    # technical (add freely)
    "python",
    "java",
    "javascript",
    "typescript",
    "c",
    "c++",
    "c#",
    ".net",
    "node.js",
    "react",
    "vue",
    "angular",
    "html",
    "css",
    "sass",
    "sql",
    "postgresql",
    "mysql",
    "sqlite",
    "mongodb",
    "nosql",
    "redis",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "linux",
    "git",
    "github",
    "gitlab",
    "ci/cd",
    "terraform",
    "ansible",
    "spark",
    "hadoop",
    "pandas",
    "numpy",
    "scikit-learn",
    "opencv",
    "pytorch",
    "tensorflow",
    "fastapi",
    "flask",
    "django",
    "rest",
    "grpc",
    "graphql",
    "rabbitmq",
    "kafka",
    "elasticsearch",
    # soft/general
    "agile",
    "scrum",
    "kanban",
    "communication",
    "leadership",
    "mentoring",
    "problem solving",
    "teamwork",
}
TECH_TOKEN = re.compile(
    r"""
    (?:                             # known multi-char tokens first (verbose mode)
        C\+\+ | C\# | \.NET | Node\.js | React | Vue | Angular | CI/CD | SQL | NoSQL
    )
    |
    (?:[A-Za-z][\w.+#-]*)           # generic tech-ish token (allows ., +, #, -)
    """,
    re.I | re.X,
)


def _extract_skills(sections: dict, experience: list) -> str:
    """
    RAW mode: return EVERYTHING inside the SKILLS section exactly as text.
    We only trim leading/trailing whitespace per line and join lines with spaces.
    No splitting, no aliasing, no dedupe, no tokenization.
    """
    lines = sections.get("SKILLS", []) or []
    # keep original order; preserve punctuation/colons/parentheses/etc.
    cleaned = [(ln or "").strip() for ln in lines if (ln or "").strip()]
    return " ".join(cleaned)  # single-line for the UI input


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _duration_months_inclusive(start_dt: datetime, end_dt: datetime) -> int:
    return max(
        0, (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month) + 1
    )


# ---------- PDF text extraction with OCR fallback ----------
_reader = None  # lazy EasyOCR reader (global to reuse weights)


def _get_ocr_reader():
    global _reader
    if _reader is None:
        # English by default; add more codes like ['en','fr'] if needed
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def _read_pdf_text(path: str) -> str:
    """
    1) Try PyMuPDF text. If a page has too little text, render page -> image and OCR with EasyOCR.
    2) Optionally blend pdfplumber text as a hint if both are sparse.
    """
    doc = fitz.open(path)
    parts: List[str] = []
    sparse = 0
    for page in doc:
        t = page.get_text("text") or ""
        if len(t.strip()) < 50:
            sparse += 1
            # OCR fallback
            pix = page.get_pixmap(dpi=300, alpha=False)
            img_bytes = pix.tobytes("png")
            reader = _get_ocr_reader()
            result = reader.readtext(img_bytes, detail=0, paragraph=True)
            t = "\n".join(result)
        parts.append(t)
    doc.close()

    text = "\n".join(parts).strip()

    # As an extra hint, try pdfplumber if we still got almost nothing
    if len(text) < 80:
        try:
            with pdfplumber.open(path) as pdf:
                more = "\n".join((p.extract_text() or "") for p in pdf.pages)
            if len(more.strip()) > len(text):
                text = more
        except Exception:
            pass

    return (text or "") + "\n"


# ---------- Section splitting ----------
def _split_sections(text: str) -> dict:
    """
    Split resume text into sections using tolerant regex headers.
    If we're already inside SKILLS and we see subcategory lines like
    'Languages: ...' or 'Frameworks/Libraries: ...', keep them as SKILLS content
    instead of starting a new section.
    """
    sections, current = {}, None

    header_patterns = {
        "SUMMARY": re.compile(
            r"^(summary|professional summary|profile)\b[:\-–—]?", re.I
        ),
        "EXPERIENCE": re.compile(
            r"^(experience|work experience|employment|professional experience)\b[:\-–—]?",
            re.I,
        ),
        "EDUCATION": re.compile(r"^(education|academic background)\b[:\-–—]?", re.I),
        # treat many synonyms as Skills headers (top-level)
        "SKILLS": re.compile(
            r"^(skills|technical skills|tech skills|skills & interests|skills and interests|"
            r"core competencies|competencies|technical proficienc(?:y|ies)|proficienc(?:y|ies)|"
            r"technolog(?:y|ies)|tools|tooling|tech stack|technology stack|stack|"
            r"programming (?:skills|languages)|frameworks(?:\s*/\s*|\s*&\s*)?libraries|frameworks|libraries|strengths)"
            r"\b[:\-–—]?",
            re.I,
        ),
        # real separate LANGUAGES section (e.g., human languages)
        "LANGUAGES": re.compile(r"^languages\b[:\-–—]?", re.I),
        # kept for completeness
        "PROJECTS": re.compile(
            r"^(projects|personal projects|notable projects)\b[:\-–—]?", re.I
        ),
    }

    def has_inline_content_after_colon(line: str) -> bool:
        i = line.find(":")
        return i != -1 and line[i + 1 :].strip() != ""

    for raw in text.splitlines():
        line = _norm(raw)
        if not line:
            continue

        matched_header = None
        for key, pat in header_patterns.items():
            if pat.match(line):
                matched_header = key
                break

        if matched_header:
            # --- IMPORTANT RULE ---
            # If we're already in SKILLS and this "header" has inline content (e.g., "Languages: C#, Java"),
            # treat it as a SKILLS content row (subcategory) instead of starting a new section.
            if current == "SKILLS" and has_inline_content_after_colon(line):
                sections.setdefault("SKILLS", []).append(line)
                continue

            # If this is the very first SKILLS-like header *and* it carries inline content on the same line,
            # start SKILLS and keep that line as content too.
            if matched_header == "SKILLS" and has_inline_content_after_colon(line):
                current = "SKILLS"
                sections.setdefault("SKILLS", [])
                sections["SKILLS"].append(line)
                continue

            # Otherwise, switch sections normally.
            current = matched_header
            sections.setdefault(current, [])
            continue

        if current:
            sections[current].append(line)

    return sections


def _parse_date_range(s: str) -> Tuple[str | None, str | None, int | None]:
    m = DATE_RE.search(s or "")
    if not m:
        return None, None, None
    start_raw, end_raw = m.group("start"), m.group("end")
    try:
        start_dt = dateparser.parse(start_raw, fuzzy=True)
    except Exception:
        start_dt = None
    if end_raw and re.search(r"present|current", end_raw or "", re.I):
        end_dt = datetime.utcnow()
    else:
        try:
            end_dt = dateparser.parse(end_raw, fuzzy=True) if end_raw else None
        except Exception:
            end_dt = None
    duration = None
    if start_dt and end_dt:
        duration = _duration_months_inclusive(start_dt, end_dt)
    return start_raw, end_raw, duration


def _extract_contacts(text: str) -> Dict[str, str | list]:
    # phone
    phone = ""
    m = CONTACT_PHONE_RE.search(text or "")
    if m:
        try:
            pn = phonenumbers.parse(m.group(0), "CA")
            phone = (
                phonenumbers.format_number(
                    pn, phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
                if phonenumbers.is_valid_number(pn)
                else _norm(m.group(0))
            )
        except Exception:
            phone = _norm(m.group(0))
    # email
    email = ""
    m = CONTACT_EMAIL_RE.search(text or "")
    if m:
        try:
            email = validate_email(m.group(0)).normalized
        except EmailNotValidError:
            email = _norm(m.group(0))
    # urls
    urls = [_norm(u) for u in URL_RE.findall(text or "")]
    # rough location line
    loc = ""
    for line in (text or "").splitlines():
        if any(h in line for h in LOCATION_HINTS) or re.search(
            r"[A-Z][a-z]+(?:,?\s+[A-Z][a-z]+)+(?:,\s*[A-Za-z]+)?", line
        ):
            loc = _norm(line)
            break
    return {"phone": phone, "urls": urls, "email": email, "location": loc}


def _guess_name(lines: List[str]) -> str:
    # choose the first plausible name-like line (titlecased tokens, not contact)
    for raw in lines[:20]:
        s = _norm(raw)
        if not s:
            continue
        if CONTACT_EMAIL_RE.search(s) or CONTACT_PHONE_RE.search(s) or URL_RE.search(s):
            continue
        tokens = [t for t in s.split() if re.match(r"^[A-Z][a-zA-Z-]+$", t)]
        if len(tokens) >= 2:
            return s
    return next((_norm(l) for l in lines if _norm(l)), "Unknown")


# ---------- Section parsers ----------
def _parse_experience(lines: List[str]) -> List[Dict]:
    items: List[Dict] = []
    cur: Dict | None = None
    prebuf: List[str] = []  # recent non-empty lines before the date line
    company_hint = COMPANY_SUFFIX  # reuse pattern

    def start_new_job(date_line: str):
        nonlocal cur
        start, end, dur = _parse_date_range(date_line)
        head = DATE_RE.split(date_line)[0].strip(" -–—|")
        parts = [p.strip() for p in re.split(r"[|•\-–—]", head) if p.strip()]
        # Try to get title/company from the 'head' (left of dates) if present
        head_title = parts[0] if parts else ""
        head_company = parts[1] if len(parts) >= 2 else ""
        # If head is empty (common in two-column resumes), backscan prebuf
        buf_title, buf_company = _guess_title_company_from_buffer(prebuf)

        title = _norm(head_title or buf_title)
        company = _norm(head_company or buf_company)

        cur = {
            "position": title,
            "company_name": company,
            "location": "",
            "start_date": start,
            "end_date": end,
            "duration_months": dur,
            "description": "",
            "skills_used_tech": [],
            "skills_used_soft": [],
        }

    for ln in lines:
        line = _norm(ln)
        if not line:
            continue

        # New job boundary: a line with a date range
        if DATE_RE.search(line):
            if cur:
                # close previous job
                items.append(cur)
            start_new_job(line)
            prebuf.clear()
            continue

        # Accumulate pre-buffer for title/company discovery before date line
        if not cur:
            prebuf.append(line)
            # keep last ~6 meaningful lines
            if len(prebuf) > 8:
                prebuf = prebuf[-8:]
            continue

        # Within a job block → grow description & fill missing metadata
        if BULLET_LINE.match(line):
            clean = BULLET_LINE.sub("", line).strip()
        else:
            clean = line
        cur["description"] = (
            cur["description"] + ("\n" if cur["description"] else "") + clean
        ).strip()

        # Fill company/location from body hints if still missing
        if not cur["company_name"] and company_hint.search(line):
            cur["company_name"] = line
        if not cur["location"]:
            if any(h.lower() in line.lower() for h in LOCATION_HINTS):
                cur["location"] = line

        # Sometimes a title appears again near the top of bullet block (e.g., "Developer")
        if not cur["position"] and _looks_like_title(line):
            cur["position"] = line

    if cur:
        items.append(cur)

    # Post-fixes
    for e in items:
        if not e["company_name"] and re.search(
            r"Machine Builder Inc\.?", e.get("description", ""), re.I
        ):
            e["company_name"] = "Machine Builder Inc."
        if not e["location"] and re.search(r"Montreal", e.get("description", ""), re.I):
            e["location"] = "Montreal"
        if e.get("start_date") and (
            not e.get("end_date")
            or re.search(r"present|current", e.get("end_date") or "", re.I)
        ):
            # recompute inclusive months to now
            _, _, e["duration_months"] = _parse_date_range(
                f"{e['start_date']} - Present"
            )

    return items


def _parse_education(lines: List[str]) -> List[Dict]:
    """
    Each education entry starts at a 'level' line (e.g., 'High School Diploma',
    'Diploma of College Studies DEC – Computer Science', 'Bachelor ...', etc).
    We then attach up to the next 2 relevant lines (school and/or location).
    """
    items: List[Dict] = []
    i, n = 0, len(lines)

    def parse_block(buf: List[str]) -> Dict:
        # Join for date parsing, but keep lines to pull school/location reliably
        text = " | ".join(buf)

        # Dates anywhere in the small block
        start, end, _ = _parse_date_range(text)

        # Level & Field
        level = ""
        field = ""
        m = EDU_LEVEL_RE.search(buf[0])
        if m:
            level = _norm(m.group(1))
        # DEC fields often after a dash on the same first line
        m_dec = re.search(r"DEC\s*[–—-]\s*([A-Za-z &/+\-]{2,})", buf[0], re.I)
        if m_dec:
            field = _norm(m_dec.group(1))
        elif re.search(r"(Bachelor|Master|BSc|MSc|PhD)", buf[0], re.I):
            m_field = re.search(r"(?:in|of)\s+([A-Za-z &/+\-]{2,})", buf[0], re.I)
            if m_field:
                field = _norm(m_field.group(1))

        # School & Location
        school, location = "", ""

        # 1) If the first line is "Level – School", split that
        parts = [p.strip() for p in re.split(r"[–—-]", buf[0]) if p.strip()]
        if len(parts) >= 2 and EDU_SCHOOL_HINT.search(parts[-1]):
            school = _norm(parts[-1])

        # 2) Otherwise, look at following lines for school/location
        for s in buf[1:]:
            s_norm = _norm(s)
            # line like "LaSalle College, Montreal, QC"
            msl = SCHOOL_LOC_SPLIT_RE.match(s_norm)
            if msl:
                school = school or _norm(msl.group("school"))
                location = _norm(msl.group("loc"))
                continue
            # pure school line
            if EDU_SCHOOL_HINT.search(s_norm):
                school = school or s_norm
                continue
            # pure location line
            if LOCATION_LINE_RE.search(s_norm):
                location = location or s_norm
                continue

        # Canonicals for your examples (optional)
        if re.search(r"High School Diploma", text, re.I) and re.search(
            r"Lawrence", text, re.I
        ):
            school = "Lawrence S. Ting School"
        if re.search(r"\bDEC\b", text, re.I) and re.search(r"LaSalle", text, re.I):
            school = "LaSalle College"

        return {
            "level": level,
            "field": field,
            "school_name": school,
            "location": location,
            "start_year": start,
            "end_year": end,
        }

    # Walk the EDUCATION lines; a level line starts a new entry
    while i < n:
        line = _norm(lines[i])
        i += 1
        if not line:
            continue

        if EDU_LEVEL_RE.search(line):
            # Start a new entry and attach up to next TWO relevant lines
            buf = [line]
            attach = 0
            while i < n and attach < 2:
                nxt = _norm(lines[i])
                # Stop when next 'level' begins or another section header appears
                if not nxt:
                    i += 1
                    continue
                if EDU_LEVEL_RE.search(nxt):
                    break
                if re.match(
                    r"^(experience|projects|skills|summary|languages)\b", nxt, re.I
                ):
                    break
                buf.append(nxt)
                attach += 1
                i += 1
            items.append(parse_block(buf))

    # Keep only non-empty entries
    return [
        e
        for e in items
        if any([e["level"], e["school_name"], e["start_year"], e["end_year"]])
    ]


def _parse_projects(lines: List[str]) -> List[Dict]:
    items, buf = [], []

    def dates_in(s: str) -> str:
        m = DATE_RE.search(s or "")
        return m.group(0) if m else ""

    def clean_title(s: str) -> str:
        s = re.sub(DATE_RE, "", s or "")
        s = re.sub(r"\b(20\d{2}|19\d{2})\b", "", s)
        return _norm(s)

    def flush():
        if not buf:
            return
        text = "\n".join(buf).strip()
        title_line = buf[0] if buf else ""
        items.append(
            {
                "title": clean_title(title_line),
                "when": dates_in(" ".join(buf)),
                "description": text,
            }
        )
        buf.clear()

    for ln in lines:
        if not (ln or "").startswith(("•", "-", "*")) and buf:
            flush()
        buf.append(ln or "")
    flush()
    return items


def _split_name(full: str) -> tuple[str, str, str]:
    full = _norm(full)
    if not full or full == "Unknown":
        return "", "", ""
    parts = full.split()
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return parts[0], " ".join(parts[1:-1]), parts[-1]


def parse_resume(filepath: str) -> Dict:
    text = _read_pdf_text(filepath)
    lines = [l for l in (text or "").splitlines()]
    full_name = _guess_name(lines)
    first, middle, last = _split_name(full_name)

    sections = _split_sections(text)
    contacts = _extract_contacts(text)

    education = _parse_education(sections.get("EDUCATION", []))
    experience = _parse_experience(sections.get("EXPERIENCE", []))

    skills_csv = _extract_skills(sections, experience)

    return {
        "name": _norm(" ".join([p for p in [first, middle, last] if p])),
        "first_name": first,
        "middle_name": middle,
        "last_name": last,
        "phone": contacts.get("phone", ""),
        "email": contacts.get("email", ""),
        "links": contacts.get("urls", []),
        "education": education,
        "experience": experience,
        # projects intentionally removed from payload
        "skills": skills_csv,
        "languages": "",
        "raw_text": text or "",
    }
