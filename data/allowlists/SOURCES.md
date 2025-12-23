# Allowlist Data Sources

This project uses external taxonomies to build **compiled allowlists** used by the ATS parser:
- `data/allowlists/compiled/tech_allowlist.txt`
- `data/allowlists/compiled/tech_aliases.json`
- `data/allowlists/compiled/skills_allowlist.txt`
- `data/allowlists/compiled/skills_aliases.json`

Raw vendor files may be large and are kept under `data/allowlists/raw/` (or stored externally and re-downloaded as needed).

---

## Source 1 — O*NET (Technology Skills)

**Used for:** large “tech / tools / software” allowlist backbone (from the `example` column).  
**Raw file(s):**
- `data/allowlists/raw/onet/31_technology_skills.sql`

**What we extract:**
- Table: `technology_skills`
- Column: `example` (e.g., “Adobe Acrobat”, “Atlassian JIRA”)
- Optional metadata: `hot_technology`, `in_demand`, `commodity_code` (for future scoring/tags)

**Version / release:**
- File name indicates: `31_technology_skills.sql` (store exact filename as version signal)

**Where it came from:**
- O*NET Database download (Technology Skills dataset)
- Project page (reference): https://www.onetcenter.org/database.html

**Downloaded:**
- YYYY-MM-DD (fill this in)

**License / terms:**
- Refer to the O*NET Database license/citation guidance:
  - https://www.onetcenter.org/license_db.html
  - https://www.onetcenter.org/citation.html

**Notes:**
- Do not edit vendor data. Any normalization happens in compiled outputs.
- We keep raw SQL unchanged for reproducibility.

---

## Source 2 — ESCO (Skills)

**Used for:** broad “skills” allowlist and aliases (preferred label + alternate labels).  
**Raw file(s):**
- `data/allowlists/raw/esco/v1.2.1/skills_en.csv`
- (optional, future) `skillHierarchy_en.csv`, `skillSkillRelations_en.csv`, `occupationSkillRelations_en.csv`

**What we extract (skills_en.csv):**
- Canonical label: `preferredLabel`
- Aliases: `altLabels` (plus `hiddenLabels` if needed)
- Optional metadata: `skillType`, `reuseLevel`, `conceptUri`, `modifiedDate`

**Dataset package:**
- “ESCO dataset – v1.2.1 – classification – en – csv” (as downloaded)

**Where it came from:**
- ESCO portal / downloads:
  - https://esco.ec.europa.eu/

**Downloaded:**
- YYYY-MM-DD (fill this in)

**License / terms:**
- Use the license information provided by the ESCO download page / documentation.

**Notes:**
- ESCO may include non-technical skills; that is expected.
- We generate compiled allowlists and aliases without modifying the raw CSV.

---

## Source 3 — GitHub Linguist (Programming Languages)

**Used for:** canonical programming language names + aliases (e.g., “C#”, “C Sharp”).  
**Raw file(s):**
- `data/allowlists/raw/linguist/languages.yml`

**What we extract:**
- Canonical names (keys in `languages.yml`)
- Aliases / alternate names (where provided)

**Where it came from:**
- GitHub Linguist repository:
  - https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml

**Downloaded:**
- YYYY-MM-DD (fill this in)

**Pinned version:**
- Commit hash or tag: (optional, recommended)

**License / terms:**
- Refer to the Linguist repository LICENSE.

---

## Build / Rebuild Notes (Compiled Outputs)

Compiled outputs are generated from the raw sources:

- `tech_allowlist.txt`
  - Unique normalized values from O*NET `technology_skills.example`
  - Plus canonical language names from `languages.yml`

- `tech_aliases.json`
  - Alias → canonical mappings (primarily from `languages.yml`)
  - Optionally expanded manually for common abbreviations (“js” → “JavaScript”)

- `skills_allowlist.txt`
  - Unique normalized values from ESCO `skills_en.csv.preferredLabel`

- `skills_aliases.json`
  - `altLabels` (and optionally `hiddenLabels`) split into alias entries mapped to the `preferredLabel`

Raw sources should remain unchanged. All normalization happens in compiled outputs so we can re-run the compilation when datasets update.
