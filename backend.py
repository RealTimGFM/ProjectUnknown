# backend.py — Flask upload -> parse -> save -> render
from flask import (
    Flask,
    request,
    render_template,
    jsonify,
    redirect,
    url_for,
    session,
    flash,
    send_from_directory,
)
import sqlite3, os, json, uuid
from resume_parser import parse_resume
from werkzeug.utils import secure_filename
from datetime import timedelta, datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

# Optional pure-Python MIME sniff (no system deps). If missing, we just skip.
try:
    import filetype  # pip install filetype
except Exception:
    filetype = None

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.permanent_session_lifetime = timedelta(minutes=30)
IDLE_TIMEOUT_MIN = 15
DB_PATH = "database.db"
ALLOWED_EXTS = {"pdf"}
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTS


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, is_admin FROM users WHERE id=?", (uid,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "username": row[1], "is_admin": bool(row[2])}


def login_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warn")
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user["is_admin"]:
            flash("Admin access required.", "error")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


@app.before_request
def enforce_idle_timeout():
    now = datetime.now(timezone.utc).timestamp()
    last = session.get("last_seen")
    if session.get("user_id"):
        if last and (now - last) > (IDLE_TIMEOUT_MIN * 60):
            # idle → logout
            session.clear()
            flash("You were logged out due to inactivity.", "info")
            return redirect(url_for("login"))
        session["last_seen"] = now


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            flash("Username and password are required.", "error")
            return redirect(url_for("signup"))
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
                (
                    username,
                    generate_password_hash(password),
                    datetime.now(timezone.utc).isoformat(),  # aware ISO8601
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("Username already exists.", "error")
            return redirect(url_for("signup"))
        # Auto-login after signup
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        uid = c.fetchone()[0]
        conn.close()
        session.clear()
        session.permanent = True
        session["user_id"] = uid
        session["last_seen"] = datetime.now(timezone.utc).timestamp()
        flash("Account created. Welcome!", "success")
        return redirect(url_for("index"))
    return render_template("auth_signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        next_url = request.args.get("next") or url_for("index")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT id, password_hash, is_admin FROM users WHERE username=?",
            (username,),
        )
        row = c.fetchone()
        conn.close()

        if not row or not check_password_hash(row[1], password):
            flash("Invalid username or password.", "error")
            return redirect(url_for("login", next=next_url))

        session.clear()
        session.permanent = True
        session["user_id"] = row[0]
        session["last_seen"] = datetime.now(timezone.utc).timestamp()
        flash("Logged in successfully.", "success")
        return redirect(next_url)
    return render_template("auth_login.html", next=request.args.get("next"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


@app.route("/reset/request", methods=["GET", "POST"])
def reset_request():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        row = c.fetchone()
        if not row:
            conn.close()
            flash("If that account exists, a reset token was created.", "info")
            return redirect(url_for("reset_request"))

        uid = row[0]
        token = secrets.token_urlsafe(24)
        expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        c.execute(
            "INSERT INTO reset_tokens (user_id, token, expires_at) VALUES (?,?,?)",
            (uid, token, expires),
        )
        conn.commit()
        conn.close()
        # For demo: show token and direct link
        flash(f"Reset token: {token}", "info")
        flash("Use the link below within 30 minutes.", "info")
        return redirect(url_for("reset_form", token=token))
    return render_template("auth_reset_request.html")


@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_form(token):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT user_id, expires_at, used FROM reset_tokens WHERE token=?", (token,)
    )
    row = c.fetchone()
    if not row:
        conn.close()
        flash("Invalid or expired token.", "error")
        return redirect(url_for("reset_request"))
    user_id, expires_at, used = row
    if used:
        conn.close()
        flash("This token was already used.", "error")
        return redirect(url_for("reset_request"))
    if datetime.now(timezone.utc) > datetime.fromisoformat(expires_at):
        conn.close()
        flash("Token expired.", "error")
        return redirect(url_for("reset_request"))

    if request.method == "POST":
        pw = request.form.get("password") or ""
        if len(pw) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for("reset_form", token=token))
        c.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (generate_password_hash(pw), user_id),
        )
        c.execute("UPDATE reset_tokens SET used=1 WHERE token=?", (token,))
        conn.commit()
        conn.close()
        flash("Password updated. Please log in.", "success")
        return redirect(url_for("login"))
    conn.close()
    return render_template("auth_reset_set.html", token=token)


@app.route("/admin")
@admin_required
def admin_home():
    return redirect(url_for("admin_candidates"))


@app.route("/admin/candidates")
@admin_required
def admin_candidates():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, email, phone FROM candidates ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return render_template("admin_candidates.html", rows=rows)


@app.post("/admin/delete/candidate/<int:cand_id>")
@admin_required
def admin_delete_candidate(cand_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM candidates WHERE id=?", (cand_id,))
    conn.commit()
    conn.close()
    flash(f"Candidate #{cand_id} deleted.", "success")
    return redirect(url_for("admin_candidates"))


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
    # users table
    c.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )"""
    )
    # password reset tokens
    c.execute(
        """CREATE TABLE IF NOT EXISTS reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )"""
    )
    conn.commit()
    # Seed a default admin once (username: admin, password: 123)
    c.execute("SELECT 1 FROM users WHERE username='admin'")
    if not c.fetchone():
        from datetime import datetime
        from werkzeug.security import generate_password_hash

        c.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?,?,?,?)",
            (
                "admin",
                generate_password_hash("123"),
                1,
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    conn.close()


@app.route("/", methods=["GET", "POST"])
@login_required
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
                parsed.get("name", ""),
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
@login_required
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
        (
            name,
            first_name,
            middle_name,
            last_name,
            phone,
            email,
            links,
            education,
            experience,
            skills,
            languages,
            cand_id,
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/admin/cvs")
@admin_required
def admin_cvs():
    base = "uploads"
    os.makedirs(base, exist_ok=True)

    # 1) get files, newest first
    files = [
        (f, os.path.getmtime(os.path.join(base, f)))
        for f in os.listdir(base)
        if f.lower().endswith(".pdf")
    ]
    files.sort(key=lambda x: x[1], reverse=True)
    files = [f for f, _ in files]

    # 2) get candidates, newest first
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, name, first_name, middle_name, last_name FROM candidates ORDER BY id DESC"
    )
    rows = c.fetchall()
    conn.close()

    # 3) zip them
    items = []
    for i, fname in enumerate(files):
        if i < len(rows):
            cid, name, fn, mn, ln = rows[i]
            full = (
                name
                or " ".join([fn or "", mn or "", ln or ""]).strip()
                or f"Candidate #{cid}"
            )
        else:
            cid, full = None, "Unknown uploader"
        items.append({"filename": fname, "candidate_id": cid, "display_name": full})

    return render_template("admin_cvs.html", items=items)


@app.route("/admin/cvs/<path:filename>")
@admin_required
def admin_download_cv(filename):
    return send_from_directory("uploads", filename, as_attachment=True)


if __name__ == "__main__":
    init_db()
    app.run(debug=False)
