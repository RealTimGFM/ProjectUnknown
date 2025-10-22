from __future__ import annotations
import re
from typing import List, Tuple
from datetime import datetime
import phonenumbers

try:
    import dateparser
except Exception:
    dateparser = None

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

    def gather_desc(start_idx: int):
        buf, j = [], start_idx
        while j < n:
            s = lines[j]
            if DATE_RE.search(s):
                break
            if _looks_like_title(s) or _looks_like_company(s):
                break
            if len(s) > 110:
                break
            buf.append(BULLET.sub("", s))
            j += 1
        return ("\n".join(buf).strip(), j)

    while i < n:
        line = lines[i]
        if not DATE_RE.search(line):
            i += 1
            continue

        start, end, months = parse_date_range(line)
        title, company, forward_used = "", "", False

        # Prefer forward look:
        if i + 1 < n:
            t1, c1 = _split_title_company_forward(lines[i + 1])
            if t1 or c1:
                title, company, forward_used = t1, c1, True
            elif _looks_like_title(lines[i + 1]):
                title = lines[i + 1]
                forward_used = True
                if i + 2 < n and _looks_like_company(lines[i + 2]):
                    company = lines[i + 2]

        # Fallback: look behind
        if not title and not company:
            ctx = lines[max(0, i - 5) : i]
            title, company = _guess_title_company_from_buffer(ctx)

        # Description starts after any forward-used line(s)
        desc_start = i + (2 if forward_used else 1)
        desc, stop = gather_desc(desc_start)

        if title or company or desc:
            items.append(
                {
                    "title": title,
                    "company": company,
                    "location": "",
                    "dates": {"start": start, "end": end, "months": months},
                    "bullets": [b for b in (desc.split("\n") if desc else []) if b],
                    "technologies": [],
                    "confidence": 0.6 if (title or company) else 0.55,
                }
            )
        i = max(i + 1, stop)

    # dedupe
    seen, uniq = set(), []
    for it in items:
        key = (
            it["company"].lower(),
            it["title"].lower(),
            it["dates"]["start"],
            it["dates"]["end"],
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


def extract_skills(lines: list[str]) -> list[str]:
    """
    English-only skills extractor from the SKILLS section.
    Returns a de-duplicated, order-preserving list of canonical technical skills.
    """
    # 1) Keep only the SKILLS block (stop on dates/long sentences/other sections)
    buf = []
    for l in lines or []:
        s = norm(l)
        if not s:
            continue
        if DATE_RE.search(s):  # skills lines usually don't have date ranges
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
    tokens = []
    for line in buf:
        tokens.extend(_split_on_separators(line))

    # 3) Canonicalize against our lexicon
    found: list[str] = []
    seen = set()
    for tok in tokens:
        # ignore obvious soft-skill singletons
        low = tok.lower()
        if low in _SOFT_SKILLS_IGNORE:
            continue

        added = False
        for canon, rx in _SKILL_PATTERNS:
            if rx.search(tok):
                if canon not in seen:
                    seen.add(canon)
                    found.append(canon)
                added = True
                break
        if added:
            continue

        # 4) If it looks like a legit tech token not in lexicon, keep the cleaned token
        # heuristics: short (<=3 words), not a sentence, has letters/numbers
        if 1 <= len(tok.split()) <= 3 and not tok.endswith("."):
            # normalize common variants
            tok = re.sub(
                r"\s+(framework|library|stack|lang(uage)?)\b", "", tok, flags=re.I
            ).strip()
            if tok and tok.lower() not in seen:
                seen.add(tok.lower())
                # preserve capitalization for things like "Git", "Linux", "Bash"
                found.append(tok)

    return found[:100]  # cap to keep UI tidy


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
