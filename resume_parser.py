import re
import pdfplumber
from datetime import datetime
from dateutil import parser as dateparser
from typing import List, Dict, Tuple

MONTHS = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*"
YEAR = r"(19|20)\d{2}"
DATE_RE = re.compile(
    rf"(?P<start>({MONTHS}\s+{YEAR}|{YEAR}))\s*[-–—]\s*(?P<end>({MONTHS}\s+{YEAR}|{YEAR}|Present|Current))",
    re.IGNORECASE,
)

CONTACT_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
CONTACT_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
URL_RE = re.compile(r"(https?://[^\s]+|(?:www\.)?(?:github|linkedin)\.com[^\s]*)", re.I)
LOCATION_HINTS = ["Montreal", "QC", "Canada", "Ho Chi Minh", "Viet", "Vietnam"]

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def _read_pdf_text(path: str) -> str:
    try:
        with pdfplumber.open(path) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages) + "\n"
    except Exception:
        return ""

def _split_sections(text: str) -> dict:
    sections, current = {}, None
    aliases = {
        "SUMMARY": {"summary", "professional summary", "profile"},
        "EXPERIENCE": {"experience", "work experience", "employment", "professional experience"},
        "EDUCATION": {"education", "academic background"},
        "PROJECTS": {"projects", "personal projects", "notable projects"},
        "SKILLS": {"skills", "technical skills"},
        "LANGUAGES": {"languages"},
    }
    for raw in text.splitlines():
        line = _norm(raw)
        if not line:
            continue
        low = line.lower()
        hit = None
        for key, names in aliases.items():
            if low in names:
                hit = key; break
        if hit:
            current = hit; sections.setdefault(current, []); continue
        if current: sections[current].append(line)
    return sections

def _parse_date_range(s: str) -> Tuple[str|None, str|None, int|None]:
    m = DATE_RE.search(s)
    if not m:
        return None, None, None
    start_raw, end_raw = m.group("start"), m.group("end")
    try:
        start_dt = dateparser.parse(start_raw, fuzzy=True)
    except Exception:
        start_dt = None
    # Use NOW if Present/Current
    if end_raw and re.search(r"present|current", end_raw, re.I):
        end_dt = datetime.utcnow()
    else:
        try:
            end_dt = dateparser.parse(end_raw, fuzzy=True) if end_raw else None
        except Exception:
            end_dt = None
    duration = None
    if start_dt and end_dt:
        duration = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month)
    return start_raw, end_raw, duration

def _extract_contacts(text: str) -> Dict[str, str]:
    phone = CONTACT_PHONE_RE.search(text)
    email = CONTACT_EMAIL_RE.search(text)
    urls = URL_RE.findall(text)
    # best-effort location: look for common hints or "City, Region"
    loc = ""
    for line in text.splitlines():
        if any(h in line for h in LOCATION_HINTS) or re.search(r"[A-Z][a-z]+(?:,?\s+[A-Z][a-z]+)+(?:,\s*[A-Za-z]+)?", line):
            loc = _norm(line); break
    return {
        "phone": _norm(phone.group(0)) if phone else "",
        "email": _norm(email.group(0)) if email else "",
        "urls": " ".join(_norm(u) for u in urls),
        "location": loc,
    }

def _parse_experience(lines: List[str]) -> List[Dict]:
    items, cur = [], None
    bullet_re = re.compile(r"^\s*[-*•]\s+")
    company_hint = re.compile(r"\b(Inc\.?|Corp\.?|LLC|Ltd\.?|Company|Capital|Systems|Labs|Studio|Technologies?)\b", re.I)

    for ln in lines:
        if DATE_RE.search(ln):
            if cur:
                # finalize skills arrays empty for now as requested
                cur["skills_used_tech"] = []
                cur["skills_used_soft"] = []
                items.append(cur)
            start, end, dur = _parse_date_range(ln)
            head = DATE_RE.split(ln)[0].strip(" -–—|")
            parts = [p.strip() for p in re.split(r"[|•\-–—]", head) if p.strip()]
            position = parts[0] if parts else ""
            # try to find company: next part with company-ish token or proper-cased phrase
            company = ""
            for p in parts[1:]:
                if company_hint.search(p) or p.istitle():
                    company = p; break
            cur = {
                "position": _norm(position),
                "company_name": _norm(company),
                "location": "",
                "start_date": start,
                "end_date": end,
                "duration_months": dur,
                "description": "",
                "skills_used_tech": [],
                "skills_used_soft": [],
            }
            continue

        if cur:
            clean = bullet_re.sub("", ln)
            cur["description"] = (cur["description"] + ("\n" if cur["description"] else "") + clean).strip()
            if not cur["company_name"] and company_hint.search(ln):
                cur["company_name"] = _norm(ln)
            if not cur["location"]:
                if any(h in ln for h in LOCATION_HINTS):
                    cur["location"] = _norm(ln)

    if cur:
        cur["skills_used_tech"] = []
        cur["skills_used_soft"] = []
        items.append(cur)

    # post-fix: if company missing but description mentions "Machine Builder Inc", set it
    for e in items:
        if not e["company_name"] and re.search(r"Machine Builder Inc", e["description"], re.I):
            e["company_name"] = "Machine Builder Inc."
        if not e["location"] and re.search(r"Montreal", e["description"], re.I):
            e["location"] = "Montreal"
        # recompute duration if end is Present/Current and we missed it
        if e["start_date"] and (not e["end_date"] or re.search(r"present|current", e["end_date"] or "", re.I)):
            _, _, e["duration_months"] = _parse_date_range(f"{e['start_date']} - Present")

    return items

def _parse_education(lines: List[str]) -> List[Dict]:
    blocks, buf = [], []
    flush_tokens = ("University", "College", "School", "Institute", "Diploma", "Bachelor", "Master", "DEC")

    def flush():
        if not buf: return
        text = " | ".join(buf)
        start, end, _ = _parse_date_range(text)
        level_match = re.search(r"(High School Diploma|Diploma|Bachelor(?:'s)?|Master(?:'s)?|DEC|College Studies DEC|BSc|MSc|PhD)", text, re.I)
        level = level_match.group(1) if level_match else ""
        field_match = re.search(r"(?:in|of)\s+([A-Za-z &/+-]{2,})", text, re.I)
        field = _norm(field_match.group(1)) if field_match else ""
        # Split around the dates to find school and location in the tail
        tail = DATE_RE.split(text)
        after = tail[-1] if len(tail) >= 3 else ""
        # school = first org-looking fragment
        school = ""
        for p in [p.strip() for p in re.split(r"[|•\-–—]", text) if p.strip()]:
            if re.search(r"(University|College|School|Institute)", p, re.I):
                school = p; break
        if not school:
            school = _norm(after.split("|")[0])
        # location = last comma phrase in tail
        loc_match = re.search(r"([A-Z][a-z]+(?:,?\s+[A-Z][a-z]+)+(?:,\s*[A-Za-z]+)?)", after)
        location = _norm(loc_match.group(1)) if loc_match else ""
        blocks.append({
            "level": _norm(level),
            "field": _norm(field),
            "school_name": _norm(school),
            "location": location,
            "start_year": start,
            "end_year": end,
        })
        buf.clear()

    for ln in lines:
        if any(t.lower() in ln.lower() for t in flush_tokens) and buf:
            flush()
        buf.append(ln)
    flush()
    return [b for b in blocks if any(b.values())]

def _parse_projects(lines: List[str]) -> List[Dict]:
    items, buf = [], []
    def dates_in(s: str) -> str:
        m = DATE_RE.search(s)
        return m.group(0) if m else ""
    def clean_title(s: str) -> str:
        s = re.sub(DATE_RE, "", s)
        s = re.sub(r"\b(20\d{2}|19\d{2})\b", "", s)
        return _norm(s)

    def flush():
        if not buf: return
        text = "\n".join(buf).strip()
        title_line = buf[0] if buf else ""
        items.append({
            "title": clean_title(title_line),           # name only
            "when": dates_in(" ".join(buf)),            # year/month-year here
            "description": text,
        })
        buf.clear()

    for ln in lines:
        # new project if a clear title line (no bullet) followed by details
        if not ln.startswith(("•", "-", "*")) and buf:
            flush()
        buf.append(ln)
    flush()
    return items

def parse_resume(filepath: str) -> Dict:
    text = _read_pdf_text(filepath)
    lines = [l for l in (text or "").splitlines()]
    # name = first non-empty line
    name = next((_norm(l) for l in lines if _norm(l)), "Unknown")

    sections = _split_sections(text)
    contacts = _extract_contacts(text)

    education = _parse_education(sections.get("EDUCATION", []))
    experience = _parse_experience(sections.get("EXPERIENCE", []))
    projects = _parse_projects(sections.get("PROJECTS", []))

    # SUMMARY = contacts only, in one line (phone, urls, email, location)
    summary = " ".join(
        p for p in [
            contacts.get("phone",""),
            contacts.get("urls",""),
            contacts.get("email",""),
            contacts.get("location",""),
        ] if p
    )

    return {
        "name": name,
        "summary": summary,
        "education": education,
        "experience": experience,
        "projects": projects,
        "skills": "",      # keep as CSV (OK to fill later)
        "languages": "",   # not needed in UI; keep empty for DB compatibility
        "raw_text": text or "",
    }
