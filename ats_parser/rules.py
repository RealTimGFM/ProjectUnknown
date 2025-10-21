from __future__ import annotations
import re
from typing import List, Tuple
from datetime import datetime
import phonenumbers
try:
    import dateparser
except Exception:
    dateparser = None

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


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def parse_date_range(s: str):
    m = DATE_RE.search(s or "")

    def to_ym(tok: str):
        if not tok:
            return None
        if re.fullmatch(PRESENT, tok, re.I):
            return "Present"
        # Try simple numeric patterns first
        if re.fullmatch(YEAR, tok):
            return f"{tok}-01"
        mm = re.match(r"(0?[1-9]|1[0-2])[-/\.]([0-9]{4})", tok)
        if mm:
            return f"{mm.group(2)}-{int(mm.group(1)):02d}"
        # Month name forms (EN/FR) via dateparser
        dt = dateparser.parse(tok, languages=["en", "fr"]) if dateparser else None
        if dt:
            return f"{dt.year}-{dt.month:02d}"
        return None

    if m:
        s_norm, e_norm = to_ym(m.group("start")), to_ym(m.group("end"))
        # compute months
        months = None
        try:
            if s_norm and e_norm and e_norm != "Present":
                ys, ms = map(int, s_norm.split("-"))
                ye, me = map(int, e_norm.split("-"))
                months = (ye - ys) * 12 + (me - ms) + 1
        except Exception:
            months = None
        return s_norm, e_norm, months

    # Fallback: split on common separators and parse both sides
    for sep in [" - ", " – ", " — ", " to ", "–", "—", "-", "– ", " — "]:
        if sep in s:
            left, right = s.split(sep, 1)
            ls, rs = to_ym(left.strip()), to_ym(right.strip())
            if ls or rs:
                months = None
                try:
                    if ls and rs and rs != "Present":
                        ys, ms = map(int, ls.split("-"))
                        ye, me = map(int, rs.split("-"))
                        months = (ye - ys) * 12 + (me - ms) + 1
                except Exception:
                    months = None
                return ls, rs, months

    return None, None, None


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
        ctx = lines[max(0, i - 5) : i]
        title, company = _guess_title_company_from_buffer(ctx)
        desc, stop = gather_desc(i + 1)
        if title or company or desc:
            items.append(
                {
                    "title": title,
                    "company": company,
                    "location": "",
                    "dates": {"start": start, "end": end, "months": months},
                    "bullets": [b for b in (desc.split("\n") if desc else []) if b],
                    "technologies": [],
                    "confidence": 0.55,
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
    # stop if we hit sentences/dates/other sections; then split on separators
    out = []
    for l in lines or []:
        s = norm(re.sub(r"^[\-•*]\s*", "", l))
        if not s:
            continue
        if DATE_RE.search(s):
            break
        if re.search(r"\b(education|experience|projects?|languages?)\b", s, re.I):
            break
        if len(s) > 80 and re.search(
            r"\b(built|designed|developed|managed|worked|implemented|created)\b",
            s,
            re.I,
        ):
            break
        out.append(s)
    tokens = []
    for chunk in re.split(r"[,;/|]", " ".join(out)):
        token = norm(chunk)
        if len(token) >= 2:
            tokens.append(token)
    tokens = list(dict.fromkeys(tokens))
    return ", ".join(tokens)[:1000]
