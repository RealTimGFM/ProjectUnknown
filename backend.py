# backend.py — Flask upload -> parse -> save -> render
from flask import Flask, request, render_template, jsonify
import sqlite3, os, json, uuid
from resume_parser import parse_resume
from werkzeug.utils import secure_filename

# Optional pure-Python MIME sniff (no system deps). If missing, we just skip.
try:
    import filetype  # pip install filetype
except Exception:
    filetype = None

app = Flask(__name__)
DB_PATH = "database.db"
ALLOWED_EXTS = {"pdf"}
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTS


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,                     -- full display name
            first_name TEXT,
            middle_name TEXT,
            last_name TEXT,
            phone TEXT,
            email TEXT,
            links TEXT,                    -- JSON array of strings
            education TEXT,                -- JSON
            experience TEXT,               -- JSON
            projects TEXT,                 -- JSON
            skills TEXT,                   -- CSV
            languages TEXT,                -- CSV
            raw_text TEXT
        )"""
    )
    conn.commit()
    conn.close()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        f = request.files.get("resume")
        if not (f and allowed_file(f.filename)):
            return render_template("index.html", candidates=[], json=json)

        os.makedirs("uploads", exist_ok=True)
        safe = secure_filename(f.filename) or "resume.pdf"
        uid = uuid.uuid4().hex
        path = os.path.join("uploads", f"{uid}_{safe}")
        f.save(path)

        # Optional lightweight MIME check (pip-only; no libmagic)
        if filetype:
            kind = filetype.guess(path)
            if not (kind and kind.mime == "application/pdf"):
                try:
                    os.remove(path)
                except Exception:
                    pass
                return render_template("index.html", candidates=[], json=json)

        parsed = parse_resume(path)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            """INSERT INTO candidates
            (name, first_name, middle_name, last_name, phone, email, links,
                education, experience, skills, languages, raw_text)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                parsed["name"],
                parsed.get("first_name", ""),
                parsed.get("middle_name", ""),
                parsed.get("last_name", ""),
                parsed.get("phone", ""),
                parsed.get("email", ""),
                json.dumps(parsed.get("links", []), ensure_ascii=False),
                json.dumps(parsed.get("education", []), ensure_ascii=False),
                json.dumps(parsed.get("experience", []), ensure_ascii=False),
                parsed.get("skills", ""),
                parsed.get("languages", ""),
                parsed.get("raw_text", ""),
            ),
        )

        conn.commit()
        conn.close()

    # fetch list
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
    "SELECT id, name, first_name, middle_name, last_name, phone, email, links, "
    "education, experience, skills, languages "
    "FROM candidates ORDER BY id DESC"
    )
    rows = c.fetchall()
    conn.close()
    return render_template("index.html", candidates=rows, json=json)


@app.post("/update/<int:cand_id>")
def update_candidate(cand_id: int):
    payload = request.get_json(force=True, silent=True) or {}
    name = payload.get("name", "")
    first_name = payload.get("first_name", "")
    middle_name = payload.get("middle_name", "")
    last_name = payload.get("last_name", "")
    phone = payload.get("phone", "")
    email = payload.get("email", "")
    links = json.dumps(payload.get("links", []), ensure_ascii=False)
    education = json.dumps(payload.get("education", []), ensure_ascii=False)
    experience = json.dumps(payload.get("experience", []), ensure_ascii=False)
    skills = payload.get("skills", "")
    languages = payload.get("languages", "")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
    """UPDATE candidates SET
        name=?, first_name=?, middle_name=?, last_name=?, phone=?, email=?, links=?,
        education=?, experience=?, skills=?, languages=? WHERE id=?""",
    (name, first_name, middle_name, last_name, phone, email, links,
    education, experience, skills, languages, cand_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})




if __name__ == "__main__":
    init_db()
    app.run(debug=False)
