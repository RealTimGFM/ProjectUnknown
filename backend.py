# backend.py
from flask import Flask, request, render_template, jsonify
import sqlite3, os, json
from resume_parser import parse_resume

app = Flask(__name__)
DB_PATH = "database.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            summary TEXT,
            education TEXT,   -- JSON
            experience TEXT,  -- JSON
            projects TEXT,    -- JSON
            skills TEXT,      -- CSV
            languages TEXT,   -- CSV
            raw_text TEXT
        )"""
    )
    conn.commit()
    conn.close()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("resume")
        if file:
            os.makedirs("uploads", exist_ok=True)
            path = os.path.join("uploads", file.filename)
            file.save(path)

            parsed = parse_resume(path)

            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                """INSERT INTO candidates 
                   (name, summary, education, experience, projects, skills, languages, raw_text)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    parsed["name"],
                    parsed.get("summary", ""),
                    json.dumps(parsed.get("education", []), ensure_ascii=False),
                    json.dumps(parsed.get("experience", []), ensure_ascii=False),
                    json.dumps(parsed.get("projects", []), ensure_ascii=False),
                    parsed.get("skills", ""),
                    parsed.get("languages", ""),
                    parsed.get("raw_text", ""),
                ),
            )
            conn.commit()
            conn.close()

    # fetch
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, name, summary, education, experience, projects, skills, languages FROM candidates ORDER BY id DESC"
    )
    rows = c.fetchall()
    conn.close()

    # pass json module so we can json.loads in template
    return render_template("index.html", candidates=rows, json=json)


@app.post("/update/<int:cand_id>")
def update_candidate(cand_id: int):
    payload = request.get_json(force=True, silent=True) or {}
    # Only accept fields we know
    name = payload.get("name", "")
    summary = payload.get("summary", "")
    education = json.dumps(payload.get("education", []), ensure_ascii=False)
    experience = json.dumps(payload.get("experience", []), ensure_ascii=False)
    projects = json.dumps(payload.get("projects", []), ensure_ascii=False)
    skills = payload.get("skills", "")
    languages = payload.get("languages", "")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """UPDATE candidates SET
           name=?, summary=?, education=?, experience=?, projects=?, skills=?, languages=?
           WHERE id=?""",
        (name, summary, education, experience, projects, skills, languages, cand_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
