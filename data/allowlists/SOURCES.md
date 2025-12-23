# Data Sources & Licenses

This project uses external datasets to build skills/technology allowlists and aliases for resume parsing.

## ESCO (European Skills, Competences, Qualifications and Occupations)
- Publisher: European Commission (DG EMPL)
- Dataset: ESCO Skills (CSV export, English)
- Files used (example): `skills_en.csv`
- Purpose in this project: large skills allowlist + aliases (preferred labels, alternative labels)
- License: CC BY 4.0 (attribution required)
- Source:
  - https://esco.ec.europa.eu/en/use-esco/download
  - https://esco.ec.europa.eu/en/about-esco/copyright

## O*NET (Occupational Information Network)
- Publisher: U.S. Department of Labor / National Center for O*NET Development
- Dataset: O*NET Database (Technology Skills table)
- Files used (example): `31_technology_skills.sql`
- Purpose in this project: technology/tool allowlist seed (examples like “Atlassian JIRA”, “Adobe Acrobat”)
- License/terms: O*NET content is available for use with required attribution (see official license/terms)
- Source:
  - https://www.onetcenter.org/database.html
  - https://www.onetcenter.org/license_db.html

## GitHub Linguist (Programming Languages List)
- Publisher: GitHub Linguist (open source)
- File used (example): `languages.yml`
- Purpose in this project: language allowlist seed and aliases for programming languages
- License: MIT
- Source:
  - https://github.com/github-linguist/linguist
  - https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml
