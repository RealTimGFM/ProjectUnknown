from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Tuple, Dict, List, Optional


# ------------------------------------------------------------
# Normalization helpers
# ------------------------------------------------------------

_WS_RE = re.compile(r"\s+")
# Keep letters/numbers plus a few tech chars (C#, C++, ASP.NET, .NET)
_KEEP_RE = re.compile(r"[^a-z0-9+#.\s]+")


def _norm_key(s: str) -> str:
    """
    Normalize a token so aliases + canon lookups are stable.

    Examples:
    - "SQL Server" -> "sql server"
    - "ASP.NET"    -> "asp.net"
    - ".NET"       -> ".net"
    - "C#"         -> "c#"
    """
    s = (s or "").strip().casefold()
    s = _KEEP_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def _find_compiled_dir() -> Optional[Path]:
    """
    Where compiled allowlists live.

    Expected files:
      - tech_allowlist.txt
      - tech_aliases.json
      - skills_allowlist.txt
      - skills_aliases.json

    Default location:
      ats_parser/compiled/
    """
    here = Path(__file__).resolve().parent
    candidates = [
        here / "compiled",
        Path.cwd() / "ats_parser" / "compiled",
        Path.cwd() / "compiled",
    ]
    for d in candidates:
        if d.exists() and d.is_dir():
            return d
    return None


def _read_allowlist_txt(path: Path) -> List[str]:
    values: List[str] = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = (raw or "").strip()
            if not line or line.startswith("#"):
                continue
            values.append(line)
    except Exception:
        return []
    return values


def _read_aliases_json(path: Path) -> Dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            # Normalize keys so lookups use _norm_key() consistently
            out: Dict[str, str] = {}
            for k, v in data.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    continue
                out[_norm_key(k)] = v.strip()
            return out
    except Exception:
        pass
    return {}


def _load_allowlist_pair(
    allowlist_filename: str,
    aliases_filename: str,
    *,
    min_enable_count: int = 200,
) -> Tuple[bool, Dict[str, str], Dict[str, str]]:
    """
    Returns:
      enabled: bool
      canon_by_key: { normalized_key -> canonical_value }
      alias_to_canon: { normalized_alias_key -> canonical_value }
    """
    compiled = _find_compiled_dir()
    if not compiled:
        return False, {}, {}

    allow_path = compiled / allowlist_filename
    alias_path = compiled / aliases_filename

    values = _read_allowlist_txt(allow_path) if allow_path.exists() else []
    aliases = _read_aliases_json(alias_path) if alias_path.exists() else {}

    canon_by_key = {_norm_key(v): v for v in values if (v or "").strip()}
    alias_to_canon: Dict[str, str] = {}

    for alias_key, canon in aliases.items():
        if not canon:
            continue
        # Prefer canonical if present; otherwise still allow it (but canonical string must be non-empty)
        alias_to_canon[alias_key] = canon

    enabled = len(canon_by_key) >= min_enable_count
    return enabled, canon_by_key, alias_to_canon


@lru_cache(maxsize=1)
def _load_compiled_tech_allowlists() -> Tuple[bool, Dict[str, str], Dict[str, str]]:
    return _load_allowlist_pair("tech_allowlist.txt", "tech_aliases.json")


@lru_cache(maxsize=1)
def _load_compiled_skills_allowlists() -> Tuple[bool, Dict[str, str], Dict[str, str]]:
    return _load_allowlist_pair("skills_allowlist.txt", "skills_aliases.json")


def _split_on_separators(s: str) -> List[str]:
    """
    Split a 'Tech:' tail or a tech-ish chunk into tokens.
    Keeps multi-word items intact if comma-separated (e.g., 'SQL Server').
    """
    if not s:
        return []
    # Normalize common separators into commas
    s = s.replace("•", ",").replace("·", ",").replace("|", ",").replace("/", ",").replace(";", ",")
    # Also split on long dashes used as separators
    s = s.replace("—", ",").replace("–", ",")
    return [t.strip() for t in s.split(",") if t.strip()]


def extract_technologies_from_text(text_or_lines) -> List[str]:
    """
    Allowlist-only technology extraction.
    - If compiled allowlist is not 'enabled' (too small/missing), returns [].
    - Otherwise, returns canonical tech strings.
    """
    enabled, canon_by_key, alias_to_canon = _load_compiled_tech_allowlists()
    if not enabled:
        return []

    if isinstance(text_or_lines, list):
        text = "\n".join([str(x) for x in text_or_lines if x is not None])
    else:
        text = str(text_or_lines or "")

    found: List[str] = []
    seen: set[str] = set()

    for tok in _split_on_separators(text):
        key = _norm_key(tok)
        canon = alias_to_canon.get(key) or canon_by_key.get(key)
        if not canon:
            continue
        ck = canon.casefold()
        if ck not in seen:
            seen.add(ck)
            found.append(canon)

    return found


# ------------------------------------------------------------
# Backward-compatible exports (what rules.py optional import expects)
# ------------------------------------------------------------

def load_allowlists():
    """
    Legacy/simple loader:
      returns (TECH_ALLOWLIST, TECH_ALIASES, SKILLS_ALLOWLIST, SKILLS_ALIASES)

    Where:
      TECH_ALLOWLIST is a list[str] (canonical values) or None
      TECH_ALIASES   is dict[norm_key(alias) -> canonical]
    """
    tech_enabled, tech_canon_by_key, tech_alias_to_canon = _load_compiled_tech_allowlists()
    skills_enabled, skills_canon_by_key, skills_alias_to_canon = _load_compiled_skills_allowlists()

    tech_list = sorted(set(tech_canon_by_key.values())) if tech_enabled else None
    skills_list = sorted(set(skills_canon_by_key.values())) if skills_enabled else None

    return tech_list, tech_alias_to_canon, skills_list, skills_alias_to_canon


TECH_ALLOWLIST, TECH_ALIASES, SKILLS_ALLOWLIST, SKILLS_ALIASES = load_allowlists()

__all__ = [
    "TECH_ALLOWLIST",
    "TECH_ALIASES",
    "SKILLS_ALLOWLIST",
    "SKILLS_ALIASES",
    "extract_technologies_from_text",
    "load_allowlists",
]
