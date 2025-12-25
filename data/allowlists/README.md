# Allowlists layout

This project separates **raw source datasets** (local-only) from **compiled artifacts** (tracked in git).

## Folders

- `data/allowlists/raw/`
  - Local-only inputs (large SQL/CSV/YAML)
  - Must be gitignored
  - Used only when running `python -m tools.build_allowlists`

- `data/allowlists/compiled/` (or `compiled/` depending on your repo)
  - Small, runtime-friendly JSON allowlists + alias maps
  - Committed to git
  - Used by the parser in “allowlist-only mode” (no unknown tech/skills)

## Policy

- CI must **never** require raw datasets.
- Runtime must work using compiled artifacts only.
- If aliases are ambiguous, they should be excluded from auto-mapping and recorded in:
  - `compiled/skills_alias_conflicts.json`

## Rebuild (local)

1) Put raw inputs into `data/allowlists/raw/...`
2) Run `python -m tools.build_allowlists`
3) Commit compiled outputs
4) Run `pytest`
