import csv
import json
import os
import re
from pathlib import Path


def norm(s: str) -> str:
    """Normalize for matching (keep canonical casing elsewhere)."""
    s = (s or "").strip()
    s = s.replace("\u2013", "-").replace("\u2014", "-")  # en/em dash
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def split_labels(s: str) -> list[str]:
    """ESCO altLabels/hiddenLabels can be delimited; handle common cases robustly."""
    if not s:
        return []
    # Common separators found in exported taxonomies
    s = s.replace("\n", ",").replace("|", ",").replace(";", ",")
    parts = [p.strip() for p in s.split(",")]
    return [p for p in parts if p]


def write_txt(path: Path, items: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(items) + "\n", encoding="utf-8")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_esco_skills(skills_csv: Path):
    canonical = {}  # norm -> canonical preferredLabel
    alias_map = {}  # norm(alias) -> canonical preferredLabel
    conflicts = {}  # norm(alias) -> list[canonical]

    with skills_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            preferred = (row.get("preferredLabel") or "").strip()
            if not preferred:
                continue

            status = (row.get("status") or "").strip().lower()
            # Safe production filter: skip clearly deprecated/obsolete entries if present
            if any(x in status for x in ["deprecated", "obsolete", "superseded"]):
                continue

            preferred_n = norm(preferred)
            canonical.setdefault(preferred_n, preferred)

            # Build aliases
            for field in ("altLabels", "hiddenLabels"):
                for alias in split_labels(row.get(field) or ""):
                    alias_n = norm(alias)
                    if not alias_n or alias_n == preferred_n:
                        continue

                    # Handle collisions deterministically + record them
                    if alias_n in alias_map and alias_map[alias_n] != preferred:
                        conflicts.setdefault(alias_n, sorted({alias_map[alias_n], preferred}))
                        continue

                    alias_map[alias_n] = preferred

    skills_allowlist = sorted(set(canonical.values()), key=lambda x: x.lower())
    # Save alias map with original alias keys? We store normalized keys for matching.
    skills_aliases = dict(sorted(alias_map.items(), key=lambda kv: kv[0]))

    return skills_allowlist, skills_aliases, conflicts


def build_onet_tech_allowlist(onet_sql: Path):
    # Parse INSERT lines, safely handling doubled quotes in SQL strings (Raiser''s)
    pat = re.compile(
        r"INSERT\s+INTO\s+technology_skills.*?VALUES\s*\(\s*'[^']*'\s*,\s*'((?:[^']|'')*)'",
        re.IGNORECASE,
    )
    out = set()

    with onet_sql.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = pat.search(line)
            if not m:
                continue
            example = m.group(1).replace("''", "'").strip()
            if example:
                out.add(example)

    return sorted(out, key=lambda x: x.lower())


def build_linguist_languages(languages_yml: Path):
    """
    Minimal YAML parser for linguist languages.yml:
    - Top-level keys (no indentation) are language names.
    - Collect aliases under each language (handles list form and inline [a,b]).
    """
    languages = []
    alias_map = {}
    current = None
    in_aliases = False

    key_pat = re.compile(r"^([^\s#].*?):\s*$")  # top-level key (not indented)
    alias_inline_pat = re.compile(r"^\s*aliases:\s*\[(.*)\]\s*$")

    with languages_yml.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")

            # New top-level key
            m = key_pat.match(line)
            if m and not line.startswith("  "):  # ensure no indentation
                current = m.group(1).strip()
                languages.append(current)
                in_aliases = False
                continue

            if current is None:
                continue

            # aliases inline: aliases: [Foo, Bar]
            m2 = alias_inline_pat.match(line)
            if m2:
                inside = m2.group(1)
                for a in [x.strip().strip("'\"") for x in inside.split(",") if x.strip()]:
                    alias_map[norm(a)] = current
                in_aliases = False
                continue

            # aliases block start
            if line.strip() == "aliases:":
                in_aliases = True
                continue

            # aliases block items
            if in_aliases:
                s = line.strip()
                if s.startswith("- "):
                    a = s[2:].strip().strip("'\"")
                    if a:
                        alias_map[norm(a)] = current
                    continue
                # end aliases block when indentation changes / next property
                if s and not s.startswith("- "):
                    in_aliases = False

    languages_allowlist = sorted(set(languages), key=lambda x: x.lower())
    alias_map = dict(sorted(alias_map.items(), key=lambda kv: kv[0]))
    return languages_allowlist, alias_map


def main():
    root = Path(__file__).resolve().parents[1]
    raw = root / "data" / "allowlists" / "raw"
    compiled = root / "data" / "allowlists" / "compiled"

    onet_sql = raw / "onet" / "31_technology_skills.sql"
    esco_skills = raw / "esco" / "v1.2.1" / "skills_en.csv"
    linguist_yml = raw / "linguist" / "languages.yml"

    if not onet_sql.exists():
        raise FileNotFoundError(f"Missing: {onet_sql}")
    if not esco_skills.exists():
        raise FileNotFoundError(f"Missing: {esco_skills}")
    if not linguist_yml.exists():
        raise FileNotFoundError(f"Missing: {linguist_yml}")

    tech_onet = build_onet_tech_allowlist(onet_sql)
    langs, lang_aliases = build_linguist_languages(linguist_yml)

    # Tech allowlist = O*NET examples + canonical language names
    tech_allowlist = sorted(set(tech_onet).union(set(langs)), key=lambda x: x.lower())
    tech_aliases = lang_aliases  # start with language aliases (expand later if needed)

    skills_allowlist, skills_aliases, skills_conflicts = build_esco_skills(esco_skills)

    write_txt(compiled / "tech_allowlist.txt", tech_allowlist)
    write_json(compiled / "tech_aliases.json", tech_aliases)
    write_txt(compiled / "skills_allowlist.txt", skills_allowlist)
    write_json(compiled / "skills_aliases.json", skills_aliases)

    if skills_conflicts:
        write_json(compiled / "skills_alias_conflicts.json", skills_conflicts)

    print("Done.")
    print(f"Tech allowlist:   {len(tech_allowlist):,}")
    print(f"Tech aliases:     {len(tech_aliases):,}")
    print(f"Skills allowlist: {len(skills_allowlist):,}")
    print(f"Skills aliases:   {len(skills_aliases):,}")
    if skills_conflicts:
        print(f"Alias conflicts:  {len(skills_conflicts):,} (see compiled/skills_alias_conflicts.json)")


if __name__ == "__main__":
    main()
