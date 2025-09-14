# Mini ATS — Structured Resume Scanner (Phase)

A minimal ATS-style web app:
- Upload a **PDF resume**.
- Backend parses sections and extracts **structured fields** (Experience, Education, Projects).
- Data is stored in **SQLite** with JSON columns.
- Web UI shows **text boxes per field**; you can edit and **save** back to DB.

---

## Features

- Section-aware parsing (SUMMARY / EXPERIENCE / EDUCATION / PROJECTS / SKILLS / LANGUAGES).
- Heuristics for dates and roles; calculates **duration (months)** when possible.
- Stores arrays (lists of dicts) as **JSON** in SQLite.
- Inline **edit & save** for each candidate.
- Safe parser (guards against missing sections / malformed bullets).

---

## Project Structure
ProjectUnknown/
├─ backend.py # Flask app + DB CRUD
├─ resume_parser.py # PDF → structured JSON (experience/education/projects)
├─ templates/
│ └─ index.html # Upload + editable cards UI
├─ uploads/ # Saved resumes (created on first upload)
├─ database.db # SQLite (auto-created)
├─ requirements.txt
└─ README.md
## Quickstart

> Tested on **Python 3.13**. Works on 3.10+.

### 1) Create venv & install deps
**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python backend.py
http://127.0.0.1:5000
# stop the app, then:
del database.db         # PowerShell
# or
rm database.db          # bash/zsh
# start the app again so it recreates the table