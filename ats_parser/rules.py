from __future__ import annotations
import re
from typing import List, Tuple
from datetime import datetime
import phonenumbers
import json
from pathlib import Path

try:
    import dateparser
except Exception:
    dateparser = None

TECH_LINE_RE = re.compile(r"^\s*(tech|tools|stack)\s*:\s*(.+)\s*$", re.I)

LOCATION_HINT = re.compile(
    r"\b("
    r"QC|ON|BC|AB|MB|SK|NS|NB|NL|PE|PEI|YT|NT|NU|CA|USA|US|UK|"
    r"Quebec|Ontario|British Columbia|Alberta|Manitoba|Saskatchewan|"
    r"Nova Scotia|New Brunswick|Newfoundland|Prince Edward Island|"
    r"Montreal|Toronto|Vancouver|Calgary|Edmonton|Ottawa|Winnipeg|"
    r"Regina|Saskatoon|Quebec City|Charlottetown"
    r")\b",
    re.I,
)

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LINK = re.compile(r"\b(?:https?://|www\.)[^\s)]+", re.I)
MONTHS = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
YEAR = r"(?:19|20)\d{2}"
NUM_MMYYYY = r"(?:0?[1-9]|1[0-2])[-/\.](?:\d{4})"
PRESENT = r"(?:Present|Current|Now|Today)"
RANGE_SEP = r"(?:\s*(?:-|–|—|to)\s*)"
DATE_TOKEN = rf"(?:{MONTHS}\s+{YEAR}|{YEAR}|{NUM_MMYYYY})"
DATE_RE = re.compile(
    rf"(?P<start>{DATE_TOKEN}){RANGE_SEP}(?P<end>{DATE_TOKEN}|{PRESENT})", re.I
)

BULLET = re.compile(r"^(\s*[-•‣∙·*]\s+)")
TITLE_HINT = re.compile(
    r"\b(senior|sr\.?|jr\.?|junior|lead|principal|staff|head|director|manager|"
    r"engineer|developer|analyst|consultant|architect|intern)\b",
    re.I,
)
COMPANY_SUFFIX = re.compile(
    r"\b(inc\.?|corp\.?|llc|ltd\.?|co\.?|company|capital|fund|bank|group|partners?|"
    r"systems?|labs?|studio|technolog(?:y|ies)|solutions?)\b",
    re.I,
)

MONTH_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

# Degree / school patterns
DEGREE_HINT = re.compile(
    r"\b("
    r"(?:bachelo[u]?r|master|msc|ma|mba|m\.?eng|b\.?sc|b\.?eng|ph\.?d|phd|doctoral|doctorate|"
    r"diploma|degree|certificat(?:e)?|dec|d\.?e\.?c|high\s+school|secondary|college\s+studies)"
    r")\b",
    re.I,
)
SCHOOL_SUFFIX = re.compile(
    r"\b(universit(?:y|é)|university|college|school|institute|academy|polytechnique|école)\b",
    re.I,
)
# ------- Skills lexicon (small but effective) -------
# canonical name -> list of regex fragments (lowercase)
_SKILL_CANON = {
    "Python": [r"\bpython\b"],
    "Java": [r"\bjava\b"],
    "JavaScript": [r"\bjavascript\b", r"\bjs\b(?!x)"],
    "TypeScript": [r"\btypescript\b", r"\bts\b(?!v)"],
    "C#": [r"\bc\#\b", r"\bc[-\s]?sharp\b"],
    "C++": [r"\bc\+\+\b"],
    "C": [r"\bc\b(?!\+\+|\s*#)\b"],
    ".NET": [r"\b\.?net(?:\s*core)?\b"],
    "Node.js": [r"\bnode(?:\.js)?\b"],
    "React": [r"\breact(?:\.js|js)?\b"],
    "Next.js": [r"\bnext(?:\.js)?\b"],
    "Vue": [r"\bvue(?:\.js|js)?\b"],
    "Angular": [r"\bangular\b"],
    "Svelte": [r"\bsvelte\b"],
    "Django": [r"\bdjango\b"],
    "Flask": [r"\bflask\b"],
    "FastAPI": [r"\bfastapi\b"],
    "Spring": [r"\bspring\b"],
    "SQL": [r"\bsql\b"],
    "PostgreSQL": [r"\bpostgres(?:ql)?\b"],
    "MySQL": [r"\bmysql\b"],
    "SQLite": [r"\bsqlite\b"],
    "MongoDB": [r"\bmongo(?:db)?\b"],
    "Redis": [r"\bredis\b"],
    "Elasticsearch": [r"\belastic(?:search)?\b"],
    "RabbitMQ": [r"\brabbitmq\b"],
    "Kafka": [r"\bkafka\b"],
    "GraphQL": [r"\bgraphql\b"],
    "REST": [r"\brest(?:ful)?\b"],
    "gRPC": [r"\bgrpc\b"],
    "HTML": [r"\bhtml?\b"],
    "CSS": [r"\bcss\b"],
    "Tailwind": [r"\btailwind\b"],
    "Sass": [r"\bsass\b|\bscss\b"],
    "Git": [r"\bgit\b"],
    "Linux": [r"\blinux\b"],
    "Docker": [r"\bdocker\b"],
    "Kubernetes": [r"\bkubernetes\b|\bk8s\b"],
    "AWS": [r"\baws\b|amazon web services"],
    "Azure": [r"\bazure\b"],
    "GCP": [r"\bgcp\b|\bgoogle cloud\b"],
    "CI/CD": [r"\bci/?cd\b", r"continuous integration", r"continuous delivery"],
    "Terraform": [r"\bterraform\b"],
    "Ansible": [r"\bansible\b"],
    "Pandas": [r"\bpandas\b"],
    "NumPy": [r"\bnumpy\b"],
    "Scikit-learn": [r"\bscikit[- ]?learn\b|\bsklearn\b"],
    "PyTorch": [r"\bpytorch\b"],
    "TensorFlow": [r"\btensorflow\b"],
    "ASP.NET": [r"\basp\.?net(?:\s*core)?\b"],
    "SQL Server": [r"\bsql\s*server\b", r"\bmssql\b"],
    "GitHub": [r"\bgithub\b"],
    "Bash": [r"\bbash\b"],
    "Shell": [r"\bshell\b", r"\bsh\b"],
    "PowerShell": [r"\bpowershell\b", r"\bps\b"],
    "VS Code": [r"\bvs\s*code\b", r"\bvisual\s+studio\s+code\b"],
    "Visual Studio": [r"\bvisual\s+studio\b"],
    "IIS": [r"\biis\b"],
    "Tomcat": [r"\btomcat\b"],
    "React Native": [r"\breact\s+native\b"],
    "Express": [r"\bexpress(?:\.js)?\b"],
    "SBERT": [r"\bsbert\b"],
    "NLP": [r"\bnlp\b"],
}

# very small soft-skills set to ignore (only removes when clearly isolated)
_SOFT_SKILLS_IGNORE = {
    "communication",
    "teamwork",
    "leadership",
    "problem solving",
    "time management",
    "adaptability",
    "collaboration",
    "customer service",
    "work ethic",
    "creativity",
}

_SKILL_PATTERNS = [
    (canon, re.compile("|".join(frags), re.I)) for canon, frags in _SKILL_CANON.items()
]

SKILLS_HEAD = re.compile(
    r"^(skills?|technical skills?|technologies|tools|tooling|"
    r"tech(?:nical)?(?:\s+stack)?|stack|"
    r"proficiencies|expertise|core (?:skills|competencies)|competenc(?:y|ies)|"
    r"programming languages?|frameworks?(?:\s*&\s*| and )?libraries|frameworks|libraries|"
    r"software|platforms|databases)\b[:\-–—]?",
    re.I,
)
NEXT_SECTION_HEAD = re.compile(
    r"^(experience|work (?:history|experience)|employment|projects?|education|languages?|certifications?)\b",
    re.I,
)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _looks_like_location(s: str) -> bool:
    s = norm(s)
    if not s:
        return False
    # Common "City, State/Province" pattern or contains known location tokens
    if re.match(r"^[A-Za-z .'\-]+,\s*[A-Za-z .'\-]+$", s):
        return True
    return bool(LOCATION_HINT.search(s))


def parse_date_range(s: str):
    """
    Handles (English only):
      - '2008 – Present'
      - '2006 – 2007'
      - 'Jun 2006 – Sep 2006'
      - 'June – Sept 2006'   (borrow year from the other side)
      - '06/2006 – 09/2006'
    """
    txt = (s or "").strip()

    # 1) Try the existing broad regex first (Month Year | Year | mm/yyyy)
    m = DATE_RE.search(txt)

    def to_ym(tok: str):
        if not tok:
            return None
        if re.fullmatch(PRESENT, tok, re.I):
            return "Present"
        if re.fullmatch(YEAR, tok):
            return f"{tok}-01"
        mm = re.match(r"(0?[1-9]|1[0-2])[-/\.]([0-9]{4})", tok)
        if mm:
            return f"{mm.group(2)}-{int(mm.group(1)):02d}"
        mn, yr = _find_month(tok), _find_year(tok)
        if mn and yr:
            return f"{yr}-{mn:02d}"
        return None

    if m:
        start_tok, end_tok = m.group("start"), m.group("end")
        s_norm = to_ym(start_tok)
        e_norm = (
            "Present" if re.fullmatch(PRESENT, end_tok or "", re.I) else to_ym(end_tok)
        )
    else:
        # 2) Fallback for 'June – Sept 2006' etc.
        s_norm = e_norm = None
        left = right = None
        for sep in [" – ", " — ", " - ", "–", "—", "-", " to "]:
            if sep in txt:
                left, right = txt.split(sep, 1)
                left, right = left.strip(), right.strip()
                break
        if left is None:
            return None, None, None

        ly, lm = _find_year(left), _find_month(left)
        ry, rm = _find_year(right), _find_month(right)
        right_present = bool(re.fullmatch(PRESENT, right, re.I))

        # borrow year from the other side when only one side has it
        if lm and not ly and ry is not None:
            ly = ry
        if rm and not ry and ly is not None and not right_present:
            ry = ly

        if ly and lm:
            s_norm = f"{ly}-{lm:02d}"
        elif ly:
            s_norm = f"{ly}-01"

        if right_present:
            e_norm = "Present"
        elif ry and rm:
            e_norm = f"{ry}-{rm:02d}"
        elif ry:
            e_norm = f"{ry}-01"

    # duration (inclusive) when both YYYY-MM present
    months = None
    try:
        if s_norm and e_norm and e_norm != "Present":
            ys, ms = map(int, s_norm.split("-"))
            ye, me = map(int, e_norm.split("-"))
            months = (ye - ys) * 12 + (me - ms) + 1
    except Exception:
        months = None

    return s_norm, e_norm, months


def extract_contacts(text: str) -> dict:
    emails = EMAIL.findall(text) or []
    links = list(dict.fromkeys(LINK.findall(text)))[:5]
    phone = None
    for m in phonenumbers.PhoneNumberMatcher(text, "CA"):
        phone = phonenumbers.format_number(
            m.number, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
        break
    # naive name guess: first line with 2-4 TitleCased tokens
    name = ""
    for ln in text.splitlines()[:12]:
        s = norm(ln)
        if not s or len(s) > 60:
            continue
        if any(ch.isdigit() for ch in s):
            continue
        toks = [t for t in s.split() if re.match(r"^[A-Z][a-zA-Z-]+$", t)]
        if 2 <= len(toks) <= 4:
            name = s
            break
    return {
        "email": emails[0] if emails else "",
        "phone": phone or "",
        "links": links,
        "name": name,
    }


def _looks_like_title(s: str) -> bool:
    s = norm(s)
    if not s or s.endswith("."):
        return False
    if _looks_like_location(s):  # <-- add this guard
        return False
    if TITLE_HINT.search(s):
        return True
    toks = [t for t in s.split() if t.isalpha()]
    if not toks:
        return False
    caps = sum(1 for t in toks if t[0].isupper() and not t.isupper())
    return caps / len(toks) >= 0.6 and len(toks) <= 7


VERB_HINT = re.compile(
    r"\b(built|designed|developed|managed|led|mentored|supported|created|owned|implemented|improved|analyzed|wrote|drove|delivered)\b",
    re.I,
)


def _looks_like_company(s: str) -> bool:
    s = norm(s)
    if not s or s.lower().startswith(("http://", "https://", "www.")):
        return False
    if VERB_HINT.search(s):
        return False
    if COMPANY_SUFFIX.search(s):
        return True
    toks = [t for t in s.split() if t.isalpha()]
    if 2 <= len(toks) <= 6:
        caps = sum(1 for t in toks if t[0].isupper() and not t.isupper())
        if caps >= 2 and len(s) <= 48:
            return True
    return False


def _guess_title_company_from_buffer(buf: list[str]) -> tuple[str, str]:
    window = [norm(x) for x in buf if norm(x)][-6:]
    title, company = "", ""
    for i in range(len(window) - 1, -1, -1):
        if _looks_like_company(window[i]):
            company = window[i]
            for j in range(i - 1, -1, -1):
                if _looks_like_title(window[j]):
                    title = window[j]
                    break
            break
    if not title:
        for i in range(len(window) - 1, -1, -1):
            if _looks_like_title(window[i]):
                title = window[i]
                break
    if not company:
        for i in range(len(window) - 1, -1, -1):
            if _looks_like_company(window[i]):
                company = window[i]
                break
    return title, company


def fallback_experience(text_or_lines) -> list[dict]:
    """
    Heuristic EXPERIENCE extractor.

    Fixes:
    - Do NOT strip bullet prefixes in gather_desc (we need them to detect bullets later).
    - Support Tech/Tools/Stack lines inside an experience block.
    - In tech allowlist mode: only keep allowlisted technologies (drop unknown tokens).
    """
    lines = [
        norm(l)
        for l in (
            text_or_lines
            if isinstance(text_or_lines, list)
            else (text_or_lines or "").splitlines()
        )
        if norm(l)
    ]

    # Tech allowlist (dynamic)
    tech_allow_enabled, tech_canon_by_key, tech_alias_to_canon = _load_compiled_tech_allowlists()

    def _add_unique(found: list[str], seen: set[str], value: str):
        k = (value or "").casefold()
        if k and k not in seen:
            seen.add(k)
            found.append(value)

    def _extract_tech_from_tail(tail: str) -> list[str]:
        if not tail:
            return []
        toks = []
        for tok in _split_on_separators(tail):
            t = (tok or "").strip()
            if not t:
                continue

            if tech_allow_enabled:
                key = _norm_key(t)
                canon = tech_alias_to_canon.get(key) or tech_canon_by_key.get(key)
                if canon:
                    toks.append(canon)
            else:
                # fallback mode (dev-friendly, no dataset)
                if 1 <= len(t.split()) <= 4 and not t.endswith("."):
                    toks.append(t)
        return toks

    def gather_desc(start_idx: int, n: int):
        """
        Collect lines belonging to the current experience item.

        Important behavior:
        - Always keep bullet lines (do not treat as title/company boundaries).
        - Always keep tech lines (Tech:/Tools:/Stack:) so we can parse technologies.
        - Stop on the next date line or a clear new header line.
        """
        buf, j = [], start_idx
        while j < n:
            s = lines[j]

            # next item begins
            if DATE_RE.search(s):
                break

            # strip bullet prefix ONLY for checking tech label
            s_no_bullet = BULLET.sub("", s).strip()

            # keep tech lines even if they look "header-ish"
            if TECH_LINE_RE.match(s_no_bullet):
                buf.append(s)
                j += 1
                continue

            # keep bullet lines
            if BULLET.match(s):
                buf.append(s)
                j += 1
                continue

            # stop when the next header-ish line begins (title/company)
            if _looks_like_title(s) or _looks_like_company(s):
                break

            # overly long lines tend to be body text or a new section
            if len(s) > 110:
                break

            buf.append(s)
            j += 1

        return buf, j

    items, i, n = [], 0, len(lines)

    while i < n:
        line = lines[i]

        # we anchor items on a date-range line
        if not DATE_RE.search(line):
            i += 1
            continue

        start, end, months = parse_date_range(line)
        title, company, forward_used = "", "", False

        # Prefer forward look (date line followed by title/company line)
        if i + 1 < n:
            t1, c1 = _split_title_company_forward(lines[i + 1])
            if t1 or c1:
                title, company, forward_used = t1, c1, True
            elif _looks_like_title(lines[i + 1]):
                title = lines[i + 1]
                forward_used = True
                if i + 2 < n and _looks_like_company(lines[i + 2]):
                    company = lines[i + 2]

        # Fallback: look behind (when title/company are above the date)
        if not title and not company:
            ctx = lines[max(0, i - 5) : i]
            title, company = _guess_title_company_from_buffer(ctx)

        # Description starts after any forward-used line(s)
        desc_start = i + (2 if forward_used else 1)
        desc_lines, stop = gather_desc(desc_start, n)

        bullets: list[str] = []
        technologies: list[str] = []
        tech_seen: set[str] = set()

        for raw in desc_lines:
            s = norm(raw)
            if not s:
                continue

            # allow "- Tech: ..." too
            s_no_bullet = BULLET.sub("", s).strip()

            mtech = TECH_LINE_RE.match(s_no_bullet)
            if mtech:
                # TECH_LINE_RE = r"^(tech|technologies|tools|stack|frameworks)\s*:\s*(.+)$"
                tail = mtech.group(2) or ""
                for t in _extract_tech_from_tail(tail):
                    _add_unique(technologies, tech_seen, t)
                continue

            # bullets
            if BULLET.match(s):
                b = BULLET.sub("", s).strip()
                if b:
                    bullets.append(b)
            else:
                # treat short non-header lines as bullet-like description
                if 0 < len(s) <= 200:
                    bullets.append(s)

        if title or company or bullets or technologies:
            items.append(
                {
                    "title": title,
                    "company": company,
                    "location": "",
                    "dates": {"start": start, "end": end, "months": months},
                    "bullets": bullets,
                    "technologies": technologies,
                    "confidence": 0.6 if (title or company) else 0.55,
                }
            )

        i = max(i + 1, stop)

    # de-dupe items
    seen, uniq = set(), []
    for it in items:
        key = (
            (it.get("company") or "").lower(),
            (it.get("title") or "").lower(),
            (it.get("dates") or {}).get("start"),
            (it.get("dates") or {}).get("end"),
        )
        if key not in seen:
            seen.add(key)
            uniq.append(it)

    return uniq



def skills_text(lines: list[str]) -> str:
    return ", ".join(extract_skills(lines))


def _split_school_location(s: str) -> tuple[str, str]:
    """Very light split: 'LaSalle College, Montreal, QC' -> ('LaSalle College','Montreal, QC')"""
    s = norm(s)
    if "," in s:
        left, right = s.split(",", 1)
        return left.strip(), right.strip()
    return s, ""


def _looks_like_school_line(s: str) -> bool:
    s = norm(s)
    # Require an explicit school keyword to avoid job titles being misread
    if SCHOOL_SUFFIX.search(s):
        return True
    # Allow common high-school patterns explicitly
    if re.search(r"\b(high school|secondary school)\b", s, re.I):
        return True
    return False


def _find_year(tok: str):
    m = re.search(r"\b(19|20)\d{2}\b", tok or "")
    return int(m.group(0)) if m else None


def _find_month(tok: str):
    t = (tok or "").lower()
    t = re.sub(r"[:;.,]+$", "", t)
    for k, v in MONTH_MAP.items():
        if re.search(rf"\b{k}\b", t):
            return v
    return None


_AT_SPLIT = re.compile(r"\s+(?:at|@)\s+", re.I)


def _split_title_company_forward(s: str) -> tuple[str, str]:
    """
    'International Transfer Officer at Friebkla Corporation, France'
    -> ('International Transfer Officer','Friebkla Corporation, France')
    """
    s = norm(s)
    m = _AT_SPLIT.search(s)
    if not m:
        return "", ""
    return s[: m.start()].strip(" -•:·—"), s[m.end() :].strip(" -•:·—")


def _parse_degree_and_field(s: str) -> tuple[str, str]:
    """
    'Diploma of College Studies DEC – Computer Science' -> ('Diploma of College Studies DEC','Computer Science')
    'High School Diploma' -> ('High School Diploma','')
    """
    s = norm(s)
    # strip any trailing date range first
    m = DATE_RE.search(s)
    if m:
        s = norm(s[: m.start()] + " " + s[m.end() :])
    parts = re.split(r"\s(?:–|—|-)\s", s, maxsplit=1)
    if len(parts) == 2:
        deg, fld = parts[0].strip(), parts[1].strip()
    else:
        deg, fld = s, ""
    return deg, fld


def fallback_education(text_or_lines) -> list[dict]:
    """
    Parse common EDUCATION layouts:

      DEGREE – FIELD
      SCHOOL, LOCATION
      YYYY-MM – Present

    Also merges cases where the degree is on one line and the school/dates
    are on the next lines, so we emit *one* item per education.
    """
    lines = [
        norm(l)
        for l in (
            text_or_lines
            if isinstance(text_or_lines, list)
            else (text_or_lines or "").splitlines()
        )
        if norm(l)
    ]

    items, i, n = [], 0, len(lines)

    while i < n:
        line = lines[i]

        # Candidate header if it has a degree keyword OR a date range
        has_deg = bool(DEGREE_HINT.search(line))
        s_start, s_end, months = parse_date_range(line)

        if not (has_deg or (s_start or s_end)):
            i += 1
            continue

        degree, field = _parse_degree_and_field(line)
        school, location = "", ""

        # ---- Look ahead up to 3 lines to capture school and/or dates
        j = i + 1
        while j < n and j <= i + 3:
            cand = lines[j]

            # If we haven't captured the school yet, try to pick it up
            if not school and _looks_like_school_line(cand):
                school, location = _split_school_location(cand)
                j += 1
                continue

            # If we don't have dates yet, try to read a date line
            if not (s_start or s_end):
                s2, e2, m2 = parse_date_range(cand)
                if s2 or e2:
                    s_start, s_end, months = s2, e2, m2
                    j += 1
                    continue

            # Stop early if another education header starts
            if DEGREE_HINT.search(cand):
                break

            j += 1

        items.append(
            {
                "degree": degree,
                "field": field,
                "school": school,
                "location": location,
                "dates": {"start": s_start, "end": s_end, "months": months},
                "gpa": None,
            }
        )

        # Skip over anything we consumed
        i = max(i + 1, j)

    # ---- Merge adjacent partial items (degree-only + school/date-only)
    merged = []
    k = 0
    while k < len(items):
        cur = items[k]
        if k + 1 < len(items):
            nxt = items[k + 1]
            # cur has degree/field but no school; nxt has school/dates but no degree → merge
            cond1 = (cur["degree"] and not cur["school"]) and (
                not nxt["degree"] and nxt["school"]
            )
            # or the reverse ordering
            cond2 = (nxt["degree"] and not nxt["school"]) and (
                not cur["degree"] and cur["school"]
            )
            if cond1 or cond2:
                a, b = (cur, nxt) if cond1 else (nxt, cur)
                merged.append(
                    {
                        "degree": a["degree"] or b["degree"],
                        "field": a["field"] or b["field"],
                        "school": b["school"] or a["school"],
                        "location": b["location"] or a["location"],
                        "dates": {
                            "start": (a["dates"]["start"] or b["dates"]["start"]),
                            "end": (a["dates"]["end"] or b["dates"]["end"]),
                            "months": (a["dates"]["months"] or b["dates"]["months"]),
                        },
                        "gpa": a.get("gpa") or b.get("gpa"),
                    }
                )
                k += 2
                continue
        merged.append(cur)
        k += 1

    return merged


def _clean_skill_token(s: str) -> str:
    # strip bullets and brackets, keep tech punctuation like + # . -
    s = BULLET.sub("", s or "")
    s = re.sub(r"[\(\)\[\]\{\}]", " ", s)
    s = re.sub(r"\b(version|v?\d+(\.\d+){0,2})\b", " ", s, flags=re.I)
    s = re.sub(
        r"\b(and|with|using|experience in|proficient in|familiar with)\b",
        " ",
        s,
        flags=re.I,
    )
    return norm(s)


def _split_on_separators(blob: str) -> list[str]:
    # split on commas, semicolons, pipes, slashes and bullets
    parts = re.split(r"[,;/|•·●◦•\u2022]+", blob)
    out = []
    for p in parts:
        p = _clean_skill_token(p)
        if p:
            # also split "X and Y" occasionally
            subparts = re.split(r"\sand\s", p, flags=re.I)
            out.extend(norm(sp) for sp in subparts if norm(sp))
    return out


# --- Allowlist (lazy-loaded) -------------------------------------------------

_ALLOWLIST_CACHE = None


def _norm_key(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def _load_compiled_allowlists():
    """
    Loads union(tech_allowlist, skills_allowlist) + union(tech_aliases, skills_aliases).
    Returns (enabled: bool, canon_by_key: dict, alias_to_canon: dict).

    enabled becomes True only if allowlists exist and are "big enough".
    """
    global _ALLOWLIST_CACHE
    if _ALLOWLIST_CACHE is not None:
        return _ALLOWLIST_CACHE

    root = Path(__file__).resolve().parents[1]  # repo root
    compiled = root / "data" / "allowlists" / "compiled"

    tech_allow = compiled / "tech_allowlist.txt"
    skills_allow = compiled / "skills_allowlist.txt"
    tech_aliases = compiled / "tech_aliases.json"
    skills_aliases = compiled / "skills_aliases.json"

    # If files aren’t present yet, stay in heuristic mode.
    if not (tech_allow.exists() and skills_allow.exists()):
        _ALLOWLIST_CACHE = (False, {}, {})
        return _ALLOWLIST_CACHE

    allow_items: list[str] = []
    for p in (tech_allow, skills_allow):
        try:
            allow_items.extend(
                [
                    ln.strip()
                    for ln in p.read_text(encoding="utf-8").splitlines()
                    if ln.strip()
                ]
            )
        except Exception:
            # Fail safe: do not break parsing if allowlist reading fails
            _ALLOWLIST_CACHE = (False, {}, {})
            return _ALLOWLIST_CACHE

    # “Big enough” gate (dynamic behavior)
    # Your build showed 9,526 tech + 13,939 skills, so this will be True in your real app.
    if len(allow_items) < 1000:
        _ALLOWLIST_CACHE = (False, {}, {})
        return _ALLOWLIST_CACHE

    canon_by_key = {_norm_key(x): x for x in allow_items}

    alias_to_canon = {}
    for ap in (tech_aliases, skills_aliases):
        if ap.exists():
            try:
                m = json.loads(ap.read_text(encoding="utf-8"))
                # keys in your compiled json are already lower-ish, but normalize anyway
                for k, v in (m or {}).items():
                    kk = _norm_key(k)
                    vv = v if isinstance(v, str) else ""
                    if not vv:
                        continue
                    # Only accept aliases that resolve to an allowed canonical term
                    if _norm_key(vv) in canon_by_key:
                        alias_to_canon[kk] = canon_by_key[_norm_key(vv)]
            except Exception:
                # ignore alias loading failures; allowlist-only still works via canon_by_key
                pass

    _ALLOWLIST_CACHE = (True, canon_by_key, alias_to_canon)
    return _ALLOWLIST_CACHE


def extract_skills(lines: list[str]) -> list[str]:
    """
    English-only skills extractor from the SKILLS section.
    Returns a de-duplicated, order-preserving list of canonical technical skills.

    Dynamic behavior:
    - If compiled allowlists are present and big enough: allowlist-only mode (no unknown tokens).
    - Otherwise: keep legacy heuristic fallback (so dev still works without the dataset).
    """
    skills_enabled, skills_canon_by_key, skills_alias_to_canon = (
        _load_compiled_allowlists()
    )
    tech_enabled, tech_canon_by_key, tech_alias_to_canon = (
        _load_compiled_tech_allowlists()
    )

    allow_enabled = bool(skills_enabled or tech_enabled)

    def add_skill(found: list[str], seen: set[str], value: str):
        k = value.casefold()
        if k not in seen:
            seen.add(k)
            found.append(value)

    def simplify_label(label: str) -> str:
        # Strip trailing parenthetical: "Python (computer programming)" -> "Python"
        return re.sub(r"\s*\([^)]*\)\s*$", "", (label or "").strip()).strip()

    def display_label(tok: str, canon: str) -> str:
        """
        Prefer clean UI labels:
        - If canon is already clean: use simplified canon.
        - If canon is a generic multi-word phrase but tok is a single tech-looking token: use tok.
        """
        tok_clean = (tok or "").strip().strip(",;")
        canon_clean = simplify_label(canon)

        # If canonical is generic (multiword) but the token is a single word (Git/SQL/etc), show token.
        if " " in canon_clean and " " not in tok_clean and 1 <= len(tok_clean) <= 24:
            # keep casing from resume; small improvement if user wrote lowercase
            if tok_clean.islower():
                # don't blindly uppercase (would make git->GIT); just capitalize
                tok_clean = tok_clean[:1].upper() + tok_clean[1:]
            return tok_clean

        return canon_clean

    # Load alias conflicts (skills only)
    alias_conflicts: set[str] = set()
    if allow_enabled:
        cached = getattr(extract_skills, "_alias_conflicts_cache", None)
        if cached is None:
            try:
                from pathlib import Path
                import json

                root = Path(__file__).resolve().parent.parent
                p = root / "compiled" / "skills_alias_conflicts.json"
                if p.exists():
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        alias_conflicts = {str(k) for k in data.keys()}
                    elif isinstance(data, list):
                        tmp = set()
                        for x in data:
                            if isinstance(x, str):
                                tmp.add(x)
                            elif isinstance(x, dict) and "alias" in x:
                                tmp.add(str(x["alias"]))
                        alias_conflicts = tmp
            except Exception:
                alias_conflicts = set()
            setattr(extract_skills, "_alias_conflicts_cache", alias_conflicts)
        else:
            alias_conflicts = cached

    # 1) Keep only the SKILLS block (stop on dates/long sentences/other sections)
    buf: list[str] = []
    for l in lines or []:
        s = norm(l)
        if not s:
            continue
        if DATE_RE.search(s):
            break
        if re.search(
            r"\b(education|experience|projects?|languages?|certifications?)\b", s, re.I
        ):
            break
        if len(s) > 100 and re.search(
            r"\b(built|designed|developed|managed|worked|implemented|created)\b",
            s,
            re.I,
        ):
            break
        buf.append(s)

    # 2) Tokenize on separators
    tokens: list[str] = []
    for line in buf:
        tokens.extend(_split_on_separators(line))

    found: list[str] = []
    seen: set[str] = set()

    # --- Allowlist-only mode ---
    if allow_enabled:
        for tok in tokens:
            low = tok.lower()
            if low in _SOFT_SKILLS_IGNORE:
                continue

            key = _norm_key(tok)

            # Prefer TECH allowlist (clean labels)
            tech_canon = tech_alias_to_canon.get(key) or tech_canon_by_key.get(key)
            if tech_canon:
                add_skill(found, seen, display_label(tok, tech_canon))
                continue

            # Skills allowlist (skip conflicting aliases)
            if key in alias_conflicts:
                continue

            skills_canon = skills_alias_to_canon.get(key) or skills_canon_by_key.get(
                key
            )
            if skills_canon:
                add_skill(found, seen, display_label(tok, skills_canon))
                continue

            # Optional: lexicon only if it resolves via allowlists
            for lex_canon, rx in _SKILL_PATTERNS:
                if rx.search(tok):
                    lk = _norm_key(lex_canon)

                    tech_canon2 = tech_alias_to_canon.get(lk) or tech_canon_by_key.get(
                        lk
                    )
                    if tech_canon2:
                        add_skill(found, seen, display_label(lex_canon, tech_canon2))
                        break

                    if lk in alias_conflicts:
                        break

                    skills_canon2 = skills_alias_to_canon.get(
                        lk
                    ) or skills_canon_by_key.get(lk)
                    if skills_canon2:
                        add_skill(found, seen, display_label(lex_canon, skills_canon2))
                    break

        return found[:100]

    # --- Fallback mode (no dataset present) ---
    for tok in tokens:
        low = tok.lower()
        if low in _SOFT_SKILLS_IGNORE:
            continue

        matched = False
        for canon, rx in _SKILL_PATTERNS:
            if rx.search(tok):
                add_skill(found, seen, canon)
                matched = True
                break
        if matched:
            continue

        if 1 <= len(tok.split()) <= 3 and not tok.endswith("."):
            tok2 = re.sub(
                r"\s+(framework|library|stack|lang(uage)?)\b", "", tok, flags=re.I
            ).strip()
            if tok2:
                add_skill(found, seen, tok2)

    return found[:100]


def extract_skills_from_text(text: str) -> list[str]:
    lines = [norm(l) for l in (text or "").splitlines() if norm(l)]
    i = 0
    while i < len(lines):
        m = SKILLS_HEAD.match(lines[i])
        if m:
            buf = []
            tail = lines[i][m.end() :].strip(" :–—-")
            if tail:
                buf.append(tail)
            j = i + 1
            while j < len(lines):
                s = lines[j]
                if NEXT_SECTION_HEAD.match(s):
                    break
                if len(s) > 140 and re.search(
                    r"\b(built|designed|developed|managed|implemented|created)\b",
                    s,
                    re.I,
                ):
                    break
                buf.append(s)
                j += 1
            return extract_skills(buf)
        i += 1
    return []


def _load_compiled_tech_allowlists():
    """
    Loads compiled/tech_allowlist.txt and compiled/tech_aliases.json
    Returns: (enabled: bool, canon_by_key: dict[str,str], alias_to_canon: dict[str,str])
    """
    cached = getattr(_load_compiled_tech_allowlists, "_cache", None)
    if cached is not None:
        return cached

    try:
        from pathlib import Path
        import json

        root = Path(__file__).resolve().parent.parent  # repo root
        compiled = root / "compiled"

        allow_path = compiled / "tech_allowlist.txt"
        alias_path = compiled / "tech_aliases.json"

        canon_by_key: dict[str, str] = {}
        alias_to_canon: dict[str, str] = {}

        if allow_path.exists():
            for line in allow_path.read_text(encoding="utf-8").splitlines():
                v = (line or "").strip()
                if not v:
                    continue
                canon_by_key[_norm_key(v)] = v

        if alias_path.exists():
            data = json.loads(alias_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for a, c in data.items():
                    if not a or not c:
                        continue
                    alias_to_canon[_norm_key(str(a))] = str(c).strip()

        enabled = len(canon_by_key) >= 200  # “big enough” safety threshold
        cached = (enabled, canon_by_key, alias_to_canon)
    except Exception:
        cached = (False, {}, {})

    setattr(_load_compiled_tech_allowlists, "_cache", cached)
    return cached


# --- Projects extraction ------------------------------------------------------

import re
import json
from pathlib import Path
from typing import Any

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_MD_LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)]+)\)", re.IGNORECASE)
_BULLET_RE = re.compile(r"^\s*[-•*]\s+")
_ROLE_RE = re.compile(r"^(role|position)\s*[:\-]\s*(.+)$", re.IGNORECASE)
_TECH_RE = re.compile(
    r"^(tech|stack|tools|technologies)\s*[:\-]\s*(.+)$", re.IGNORECASE
)

# headings to ignore if they appear in the passed lines
_IGNORE_HEADINGS = {
    "projects",
    "selected projects",
    "personal projects",
    "academic projects",
    "side projects",
    "key projects",
    "experience",
    "work experience",
    "professional experience",
    "employment",
    "skills",
    "education",
    "certifications",
    "certs",
    "languages",
    "summary",
}

# job titles that must NOT be treated as projects
_JOB_TITLES = [
    "project manager",
    "project lead",
    "project coordinator",
    "project director",
    "program manager",
    "product manager",
    "scrum master",
]

# Optional allowlist module (if you have it). Safe fallback if not present.
try:
    from .allowlists import TECH_ALLOWLIST, TECH_ALIASES  # type: ignore
except Exception:  # pragma: no cover
    TECH_ALLOWLIST = None
    TECH_ALIASES = {}


def _norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _is_bullet(s: str) -> bool:
    return bool(_BULLET_RE.match(s or ""))


def _strip_bullet(s: str) -> str:
    return _BULLET_RE.sub("", s or "").strip()


def _split_tokens(s: str) -> list[str]:
    raw = re.split(r"[;,|]\s*|\s*/\s*", s or "")
    out: list[str] = []
    for t in raw:
        t = _norm_space(t)
        if t:
            out.append(t)
    return out


def _collect_links(line: str) -> list[str]:
    links: list[str] = []
    links.extend(_MD_LINK_RE.findall(line or ""))
    links.extend(_URL_RE.findall(line or ""))
    cleaned = []
    for u in links:
        cleaned.append((u or "").rstrip(").,;]}>"))
    return cleaned


def _is_heading_line(line: str) -> bool:
    s = _norm_space(line).casefold()
    return s in _IGNORE_HEADINGS


def _looks_like_experience_title(line: str) -> bool:
    """
    Treat as EXPERIENCE (not PROJECTS) if line begins with a known job title and
    appears to mention a company via separator:
      - "Project Manager at ABC Corp"
      - "Project Manager — ABC Corp"
      - "Project Manager - ABC Corp"
    """
    s = _strip_bullet(_norm_space(line)).casefold()
    if not s:
        return False

    for jt in _JOB_TITLES:
        if s.startswith(jt):
            # company signal separators
            if " at " in s:
                return True
            if " — " in s or " – " in s or " - " in s:
                return True
    return False


def _canonical_tech(token: str) -> str | None:
    t = _norm_space(token)
    if not t:
        return None

    key = t.casefold()
    if isinstance(TECH_ALIASES, dict) and key in TECH_ALIASES:
        t = TECH_ALIASES[key]

    if TECH_ALLOWLIST is not None:
        allow = {x.casefold() for x in TECH_ALLOWLIST}
        if t.casefold() not in allow:
            return None

    return t


def _parse_dates_line(line: str) -> dict[str, str | None] | None:
    """
    Uses your existing parse_date_range() from rules.py.
    """
    try:
        ds = parse_date_range(line)  # noqa: F821 (already exists in this module)
    except Exception:
        return None

    if not ds:
        return None

    if isinstance(ds, dict):
        return {"start": ds.get("start"), "end": ds.get("end")}

    start = getattr(ds, "start", None)
    end = getattr(ds, "end", None)
    if start is None and end is None:
        return None
    return {"start": start, "end": end}


def _parse_title_role_dates(
    title_line: str,
) -> tuple[str, str | None, dict[str, str | None]]:
    """
    Title line examples:
      - "StockAI — Personal Project (2024-01 to Present)"
      - "My App - Backend Developer | https://..."
      - "Portfolio Website (2023)"
    We want:
      title, role (optional), dates {start,end}
    """
    line = _strip_bullet(_norm_space(title_line))

    # pull out parenthetical chunk(s) for date parsing
    dates = {"start": None, "end": None}
    m = re.search(r"\(([^)]+)\)", line)
    if m:
        d = _parse_dates_line(m.group(1))
        if d:
            dates = d
        # remove that parenthetical from role text
        line_wo_paren = (line[: m.start()] + line[m.end() :]).strip()
    else:
        line_wo_paren = line

    # split on dash variants to infer role
    role = None
    title = line_wo_paren

    for sep in ["—", "–", "-"]:
        if sep in line_wo_paren:
            left, right = line_wo_paren.split(sep, 1)
            left = _norm_space(left)
            right = _norm_space(right)
            if left:
                title = left
            if right:
                # if right is clearly a role phrase, store it
                role = right
            break

    title = _norm_space(title)
    if role is not None:
        role = _norm_space(role)
        if not role:
            role = None

    return title, role, dates


# -------------------- PROJECTS extraction --------------------

PROJECTS_HEAD = re.compile(
    r"^(projects|selected projects|personal projects|academic projects|side projects|key projects)\b",
    re.I,
)

LINK_LINE_RE = re.compile(
    r"^(?:links?|link|repo|repository|github)\s*:\s*(.+)$",
    re.I,
)

# Reuse your existing TECH_LINE_RE if you already have it.
# If you DON'T have TECH_LINE_RE in rules.py, keep this definition.
try:
    TECH_LINE_RE
except NameError:
    TECH_LINE_RE = re.compile(r"^(tech|stack|tools|technologies?)\s*:\s*(.+)$", re.I)

_URL_RE = re.compile(r"https?://\S+")


def _parse_project_heading(line: str) -> tuple[str, str, dict]:
    """
    Parse a project heading line into: (title, role, dates_dict)

    Examples:
      "StockAI — Personal Project (2024-01 to Present)"
      "My App - Capstone Project (2023)"
      "Tooling Dashboard — (2022-05 to 2022-09)"
    """
    s = norm(line)
    # remove leading bullets if present
    s = re.sub(r"^[\-\*\u2022]\s+", "", s).strip()

    # dates: let your existing parse_date_range do the hard work
    start, end, _months = parse_date_range(s)
    dates = {"start": start, "end": end}

    # remove a trailing (...) chunk if it likely contains dates
    # (prevents role/title pollution)
    s2 = s
    m = re.search(r"\(([^)]*)\)\s*$", s2)
    if m:
        tail = m.group(1)
        if re.search(r"\d{4}|\bpresent\b|\bcurrent\b", tail, re.I):
            s2 = s2[: m.start()].strip()

    # split title vs role on a dash separator (—, –, or " - ")
    parts = re.split(r"\s+[—–-]\s+", s2, maxsplit=1)
    title = parts[0].strip()
    role = parts[1].strip() if len(parts) == 2 else ""

    return title, role, dates


def extract_projects(lines: list[str]) -> list[dict]:
    """
    Contract:
      returns list[dict] with keys:
        - title (str)
        - role (str)
        - tech_stack (list[str])      # allowlist-filtered when dataset is available
        - links (list[str])
        - dates ({start,end})
        - bullets (list[str])
    """
    raw = [norm(x) for x in (lines or []) if norm(x)]
    if not raw:
        return []

    # Disambiguation: only parse when the *block itself* is a Projects section.
    # This prevents EXPERIENCE lines like "Project Manager — ..." from being misread.
    if not PROJECTS_HEAD.match(raw[0]):
        return []

    projects: list[dict] = []
    cur: dict | None = None

    def _start_new_project(heading_line: str):
        nonlocal cur
        title, role, dates = _parse_project_heading(heading_line)

        # If we somehow can't get a title, do not start an item.
        if not title:
            return

        cur = {
            "title": title,
            "role": role or "",  # keep string (not None)
            "tech_stack": [],
            "links": [],
            "dates": dates,
            "bullets": [],
        }
        projects.append(cur)

    # Iterate after the heading line
    for line in raw[1:]:
        if not line:
            continue

        # New project heading heuristic:
        # - Not a Tech/Link line
        # - Not a pure bullet line
        # - Often contains a dash separator or parentheses with dates
        if (
            not TECH_LINE_RE.match(line)
            and not LINK_LINE_RE.match(line)
            and not re.match(r"^[\-\*\u2022]\s+", line)
            and (re.search(r"\s+[—–-]\s+", line) or DATE_RE.search(line))
        ):
            _start_new_project(line)
            continue

        # If we haven't started a project yet, ignore detail lines.
        if cur is None:
            continue

        # Tech line -> tokenize -> allowlist filter
        mtech = TECH_LINE_RE.match(line)
        if mtech:
            tech_raw = mtech.group(2).strip()
            tokens = _split_on_separators(tech_raw)
            tech = _filter_tech_allowlist(
                tokens
            )  # drops unknown tokens in allowlist mode
            for t in tech:
                if t not in cur["tech_stack"]:
                    cur["tech_stack"].append(t)
            continue

        # Link line (or any URLs)
        mlink = LINK_LINE_RE.match(line)
        if mlink:
            urls = _URL_RE.findall(mlink.group(1))
        else:
            urls = _URL_RE.findall(line)

        if urls:
            for u in urls:
                if u not in cur["links"]:
                    cur["links"].append(u)
            continue

        # Bullet / description line
        b = re.sub(r"^[\-\*\u2022]\s+", "", line).strip()
        if b:
            cur["bullets"].append(b)

    # Drop empty shells (no title already filtered; this is extra safety)
    projects = [p for p in projects if p.get("title")]

    return projects


def _split_simple_tokens(s: str) -> list[str]:
    # Split common “tech stack” separators: commas, pipes, slashes, bullets
    parts = re.split(r"[,\|/;•·]+", s or "")
    out = []
    for p in parts:
        p = (p or "").strip()
        if not p:
            continue
        # remove trailing punctuation
        p = re.sub(r"[.\s]+$", "", p).strip()
        if p:
            out.append(p)
    return out


_TECH_ALLOW_CACHE = None
_SKILLS_ALLOW_CACHE = None


def _find_compiled_dir() -> Path | None:
    """
    Support both layouts:
    - repo_root/compiled
    - repo_root/data/allowlists/compiled
    """
    repo_root = Path(__file__).resolve().parents[1]
    c1 = repo_root / "compiled"
    c2 = repo_root / "data" / "allowlists" / "compiled"
    if c1.exists():
        return c1
    if c2.exists():
        return c2
    return None


def _read_allowlist_values(path: Path) -> list[str]:
    """
    Allow either:
    - .txt (one per line)
    - .json (either list[str] or dict[str, ...] where keys are canonical labels)
    """
    if not path.exists():
        return []

    if path.suffix.lower() == ".txt":
        return [
            ln.strip()
            for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]

    if path.suffix.lower() == ".json":
        obj = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(obj, list):
            return [str(x).strip() for x in obj if str(x).strip()]
        if isinstance(obj, dict):
            return [str(k).strip() for k in obj.keys() if str(k).strip()]

    return []


def _load_allowlist_pair(base_name: str, aliases_name: str):
    """
    Robustly find allowlist in either .txt or .json if caller passes a .txt name.
    """
    compiled_dir = _find_compiled_dir()
    if not compiled_dir:
        return False, {}, {}

    base_path = compiled_dir / base_name
    # fallback: if tech_allowlist.txt is missing, try tech_allowlist.json
    if not base_path.exists() and base_path.suffix.lower() == ".txt":
        alt = base_path.with_suffix(".json")
        if alt.exists():
            base_path = alt

    aliases_path = compiled_dir / aliases_name

    values = _read_allowlist_values(base_path)
    if not values:
        return False, {}, {}

    canon_by_key = {_norm_key(v): v for v in values}

    alias_to_canon = {}
    if aliases_path.exists():
        data = json.loads(aliases_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for a, c in data.items():
                if not a or not c:
                    continue
                alias_to_canon[_norm_key(a)] = str(c).strip()

    enabled = len(canon_by_key) >= 200
    return enabled, canon_by_key, alias_to_canon


def _load_compiled_tech_allowlists():
    return _load_allowlist_pair("tech_allowlist.txt", "tech_aliases.json")


def _load_compiled_skills_allowlists():
    return _load_allowlist_pair("skills_allowlist.json", "skills_aliases.json")


TECH_ALLOWLIST_ENABLED, TECH_ALLOWLIST, TECH_ALIAS_TO_CANON = (
    _load_compiled_tech_allowlists()
)


def _pretty_label(
    canon: str, skills_canon_by_key: dict, skills_alias_to_canon: dict
) -> str:
    """
    If the canonical label is a long ESCO label like:
      "Python (computer programming)"
    but we have an alias "python" -> "Python", prefer short.
    """
    if not canon:
        return canon

    # If it's already short-ish, keep as-is.
    if len(canon) <= 30 and "(" not in canon:
        return canon

    key = _norm_key(canon)
    # If canon exists in skills allowlist, keep canon unless we can find a simpler alias.
    # We keep this conservative to avoid breaking allowlist semantics.
    return canon


def _filter_tech_allowlist(tokens: list[str]) -> list[str]:
    """
    Canonicalize + filter tech tokens using:
    - tech allowlist (primary)
    - skills allowlist (secondary fallback)
    If allowlists are not available, returns a conservative de-duped list.
    """
    tech_enabled, tech_canon_by_key, tech_alias_to_canon = (
        _load_compiled_tech_allowlists()
    )
    skills_enabled, skills_canon_by_key, skills_alias_to_canon = (
        _load_compiled_skills_allowlists()
    )

    allow_enabled = bool(tech_enabled or skills_enabled)

    out: list[str] = []
    seen: set[str] = set()

    for tok in tokens or []:
        tok = (tok or "").strip()
        if not tok:
            continue

        # If allowlists are not enabled, just de-dupe conservatively.
        if not allow_enabled:
            k = tok.casefold()
            if k not in seen:
                seen.add(k)
                out.append(tok)
            continue

        key = _norm_key(tok)

        canon = None
        if tech_enabled:
            canon = tech_alias_to_canon.get(key) or tech_canon_by_key.get(key)

        if not canon and skills_enabled:
            canon = skills_alias_to_canon.get(key) or skills_canon_by_key.get(key)

        if not canon:
            # allowlist-only mode: drop unknowns
            continue

        label = canon
        if skills_enabled and canon in skills_canon_by_key.values():
            label = _pretty_label(canon, skills_canon_by_key, skills_alias_to_canon)

        lk = label.casefold()
        if lk not in seen:
            seen.add(lk)
            out.append(label)

    return out
