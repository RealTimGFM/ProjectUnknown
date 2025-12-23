import re


def split_sections(text: str) -> dict[str, list[str]]:
    """
    Split resume text into section buckets based on heading lines.

    Design goals:
    - Prevent false section switches (e.g., "Software Developer" must NOT trigger SKILLS).
    - Keep PROJECTS separate from EXPERIENCE.
    - Allow headings like "Skills: Python, SQL" (tail captured into section lines).
    """

    # Require heading lines to be:
    # - exact heading, OR heading followed by ":" / "-" / "–" / "—"
    # This avoids matching normal content like "Software Developer" or "Project Manager".
    def _hdr(pattern: str) -> re.Pattern:
        return re.compile(rf"^{pattern}(?:\s*[:\-–—]\s*|$)", re.I)

    SECTION_PATTERNS = {
        "SUMMARY": _hdr(r"(summary|professional summary|profile)"),

        # IMPORTANT: do NOT include "projects" here.
        # We allow "Project Experience" as EXPERIENCE (common heading), but not "Projects".
        "EXPERIENCE": _hdr(
            r"(experience|work (?:history|experience)|employment|professional experience|project experience)"
        ),

        "EDUCATION": _hdr(r"(education|academic background|studies)"),

        # Note: keep this conservative to avoid false positives on normal lines.
        "SKILLS": _hdr(
            r"(skills?|technical skills?|technologies|tools|tooling|"
            r"tech(?:nical)?(?:\s+stack)?|stack|"
            r"proficiencies|expertise|core (?:skills|competencies)|competenc(?:y|ies)|"
            r"programming languages?|frameworks?(?:\s*&\s*| and )?libraries|libraries|"
            r"databases)"
        ),

        "CERTS": _hdr(r"(certifications?|licenses?)"),
        "LANGUAGES": _hdr(r"(languages?)"),

        # Projects headings (expanded a bit, but still strict)
        "PROJECTS": _hdr(
            r"(projects|selected projects|personal projects|academic projects|side projects|notable projects|key projects|relevant projects)"
        ),
    }

    lines = [l.rstrip() for l in text.splitlines()]
    cur = None
    out = {k: [] for k in SECTION_PATTERNS.keys()}
    out.setdefault("OTHER", [])

    for ln in lines:
        s = re.sub(r"\s+", " ", (ln or "").strip())
        if not s:
            continue

        switched = False
        for key, rx in SECTION_PATTERNS.items():
            m = rx.match(s)
            if m:
                cur = key
                switched = True

                # Keep anything after the heading (e.g. "Skills: C#, Java")
                tail = s[m.end() :].strip(" :–—-")
                if tail:
                    out[cur].append(tail)
                break

        if not switched:
            (out[cur] if cur else out["OTHER"]).append(s)

    return out
