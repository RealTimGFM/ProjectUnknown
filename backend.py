# backend.py — Flask upload -> parse -> save -> render
from flask import (
    Flask,
    abort,
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
from functools import wraps


# Optional pure-Python MIME sniff (no system deps). If missing, we just skip.
try:
    import filetype  # pip install filetype
except Exception:
    filetype = None
SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    active        INTEGER NOT NULL DEFAULT 1,      -- US22/US26: deactivate flag
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,                  -- NEW: owner (US15/US27)
    name        TEXT,
    first_name  TEXT,
    middle_name TEXT,
    last_name   TEXT,
    phone       TEXT,
    email       TEXT,
    links       TEXT,                              -- JSON string
    education   TEXT,                              -- JSON string
    experience  TEXT,                              -- JSON string
    skills      TEXT,
    languages   TEXT,
    raw_text    TEXT,
    filepath    TEXT,                              -- NEW: saved file path
    created_at  TEXT NOT NULL,                     -- NEW: audit/sorting
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Optional: if you already support password resets
CREATE TABLE IF NOT EXISTS reset_tokens (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    token      TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""
app = Flask(__name__)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("COOKIE_SECURE", "0") == "1"),
)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.permanent_session_lifetime = timedelta(minutes=30)
IDLE_TIMEOUT_MIN = 15
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
DB_PATH  = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "database.db"))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
ALLOWED_EXTS = {"pdf", "docx"}
os.makedirs(UPLOAD_DIR, exist_ok=True)
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

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warn")
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        u = current_user()
        if not (u and u.get("is_admin")):
            flash("Admin access required.", "error")
            # optional: send them back to where they tried to go
            return redirect(url_for("login", next=request.path))
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
            "SELECT id, password_hash, is_admin, active FROM users WHERE username=?",
            (username,),
        )
        row = c.fetchone()
        conn.close()

        if not row or not check_password_hash(row[1], password):
            import time

            time.sleep(0.5)
            flash("Invalid username or password.", "error")
            return redirect(url_for("login", next=next_url))

        if not row[3]:
            flash("Account is deactivated. Contact admin.", "error")
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
    c.execute("SELECT filepath FROM candidates WHERE id=?", (cand_id,))
    row = c.fetchone()
    if row and row[0] and os.path.exists(row[0]):
        try:
            os.remove(row[0])
        except Exception:
            pass
    c.execute("DELETE FROM candidates WHERE id=?", (cand_id,))
    conn.commit()
    conn.close()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA_SQL)
        c = conn.cursor()

        # ensure an admin user called 'admin' exists AND is admin+active
        from datetime import datetime, timezone
        from werkzeug.security import generate_password_hash

        c.execute("SELECT id, is_admin, active FROM users WHERE username=?", ("admin",))
        row = c.fetchone()
        if not row:
            c.execute(
                """
                INSERT INTO users (username, password_hash, is_admin, active, created_at)
                VALUES (?,?,?,?,?)
                """,
                (
                    "admin",
                    generate_password_hash("123"),
                    1,
                    1,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        else:
            # elevate if needed
            c.execute(
                "UPDATE users SET is_admin=1, active=1 WHERE username=?", ("admin",)
            )
        conn.commit()


@app.route("/", methods=["GET"])
@login_required
def index():
    # fetch list (OPTIONAL: show only the current user's CVs)
    uid = current_user()["id"]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        SELECT id, name, first_name, middle_name, last_name, phone, email, links,
               education, experience, skills, languages
        FROM candidates
        WHERE user_id=?
        ORDER BY id DESC
    """,
        (uid,),
    )
    rows = c.fetchall()
    conn.close()
    return render_template("index.html", candidates=rows, json=json, user=current_user())


@app.post("/update/<int:cand_id>")
@login_required
def update_candidate(cand_id: int):
    uid = current_user()["id"]
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id FROM candidates WHERE id=?", (cand_id,))
        row = c.fetchone()
        if not row or row[0] != uid:
            abort(403)

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
    base = UPLOAD_DIR
    os.makedirs(base, exist_ok=True)

    # 1) get files, newest first
    files = [
        (f, os.path.getmtime(os.path.join(base, f)))
        for f in os.listdir(base)
        if f.lower().endswith((".pdf", ".docx"))
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


@app.post("/upload")
@login_required
def upload():
    f = request.files.get("file")
    if not f:
        flash("No file")
        return redirect(url_for("index"))

    # extension guard
    ext = os.path.splitext(f.filename)[1].lower().lstrip(".")
    if ext not in ALLOWED_EXTS:
        flash("Unsupported file type")
        return redirect(url_for("index"))

    # save file: uploads/<userId>_<safe_name>
    uid = current_user()["id"]
    safe_name = secure_filename(f.filename)
    save_dir = UPLOAD_DIR
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"{uid}_{safe_name}")
    f.save(save_path)

    # parse resume
    try:
        parsed = parse_resume(save_path)
    except Exception as e:
        # cleanup on failure
        try:
            os.remove(save_path)
        except Exception:
            pass
        flash(f"Parse failed: {e}")
        return redirect(url_for("index"))

    # --- normalize fields for DB ---
    links_json = json.dumps(parsed.get("links", []), ensure_ascii=False)
    education_json = json.dumps(parsed.get("education", []), ensure_ascii=False)
    experience_json = json.dumps(parsed.get("experience", []), ensure_ascii=False)

    skills_val = parsed.get("skills", "")
    if isinstance(skills_val, list):
        skills_val = ", ".join(map(str, skills_val))

    # you said you don't need to parse languages
    languages_val = ""  # store empty; no list/JSON here

    raw_text_val = parsed.get("raw_text", "")
    now = datetime.now(timezone.utc).isoformat()

    # insert
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO candidates (
              user_id, name, first_name, middle_name, last_name,
              phone, email, links, education, experience,
              skills, languages, raw_text, filepath, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                uid,
                parsed.get("name", ""),
                parsed.get("first_name", ""),
                parsed.get("middle_name", ""),
                parsed.get("last_name", ""),
                parsed.get("phone", ""),
                parsed.get("email", ""),
                links_json,
                education_json,
                experience_json,
                skills_val,
                languages_val,
                raw_text_val,
                save_path,
                now,
            ),
        )
        conn.commit()

    flash("CV uploaded")
    return redirect(url_for("index"))


def get_upload_counts():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        rows = c.execute(
            """
            SELECT u.id, u.username, u.active, u.is_admin, COUNT(c.id) AS uploads
            FROM users u
            LEFT JOIN candidates c ON c.user_id = u.id
            GROUP BY u.id, u.username, u.active, u.is_admin
            ORDER BY uploads DESC, u.username ASC
            """
        ).fetchall()
    return rows


@app.post("/reupload/<int:cand_id>")
@login_required
def reupload_cv(cand_id: int):
    uid = current_user()["id"]
    f = request.files.get("file")
    if not f:
        flash("No file to re-upload.", "error")
        return redirect(url_for("index"))

    ext = os.path.splitext(f.filename)[1].lower().lstrip(".")
    if ext not in {"pdf", "docx"}:
        flash("Unsupported file type", "error")
        return redirect(url_for("index"))

    # owner/admin check + get old filepath
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, filepath FROM candidates WHERE id=?", (cand_id,))
        row = c.fetchone()
        if not row:
            flash("Candidate not found.", "error")
            return redirect(url_for("index"))
        owner_id, old_path = row
        u = current_user()
        if not (u["is_admin"] or owner_id == uid):
            abort(403)

    # save new file
    safe_name = secure_filename(f.filename)
    save_dir =  UPLOAD_DIR
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, f"{uid}_{safe_name}")
    f.save(save_path)

    # parse
    try:
        parsed = parse_resume(save_path)
    except Exception as e:
        try:
            os.remove(save_path)
        except Exception:
            pass
        flash(f"Parse failed: {e}", "error")
        return redirect(url_for("index"))

    # --- normalize fields for DB ---
    links_json = json.dumps(parsed.get("links", []), ensure_ascii=False)
    education_json = json.dumps(parsed.get("education", []), ensure_ascii=False)
    experience_json = json.dumps(parsed.get("experience", []), ensure_ascii=False)

    skills_val = parsed.get("skills", "")
    if isinstance(skills_val, list):
        skills_val = ", ".join(map(str, skills_val))

    # you said you don't need to parse languages
    languages_val = ""  # store empty; no list/JSON here

    raw_text_val = parsed.get("raw_text", "")
    now = datetime.now(timezone.utc).isoformat()

    # update candidate
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            """
            UPDATE candidates SET
              name=?, first_name=?, middle_name=?, last_name=?,
              phone=?, email=?, links=?, education=?, experience=?,
              skills=?, languages=?, raw_text=?, filepath=?, created_at=?
            WHERE id=?
            """,
            (
                parsed.get("name", ""),
                parsed.get("first_name", ""),
                parsed.get("middle_name", ""),
                parsed.get("last_name", ""),
                parsed.get("phone", ""),
                parsed.get("email", ""),
                links_json,
                education_json,
                experience_json,
                skills_val,
                languages_val,
                raw_text_val,
                save_path,
                now,
                cand_id,
            ),
        )
        conn.commit()

    # remove old file after successful update
    if old_path and os.path.exists(old_path):
        try:
            os.remove(old_path)
        except Exception:
            pass

    flash("CV re-uploaded & parsed.", "success")
    return redirect(url_for("index"))


@app.post("/account/delete")
@login_required
def account_delete():
    uid = current_user()["id"]
    pw = request.form.get("password") or ""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT password_hash FROM users WHERE id=?", (uid,))
        row = c.fetchone()
        if not row or not check_password_hash(row[0], pw):
            flash("Password incorrect.", "error")
            return redirect(url_for("index"))
        c.execute("SELECT filepath FROM candidates WHERE user_id=?", (uid,))
        for (fp,) in c.fetchall():
            if fp and os.path.exists(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass
        c.execute("DELETE FROM users WHERE id=?", (uid,))
        conn.commit()
    session.clear()
    flash("Account and all uploads deleted.", "success")
    return redirect(url_for("login"))


@app.post("/cv/delete/<int:cand_id>")
@login_required
def delete_cv(cand_id: int):
    uid = current_user()["id"]
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, filepath FROM candidates WHERE id=?", (cand_id,))
        row = c.fetchone()
        if not row:
            flash("Not found.", "error")
            return redirect(url_for("index"))
        owner_id, fpath = row
        u = current_user()
        if not (u["is_admin"] or owner_id == uid):
            abort(403)
        if fpath and os.path.exists(fpath):
            try:
                os.remove(fpath)
            except Exception:
                pass
        c.execute("DELETE FROM candidates WHERE id=?", (cand_id,))
        conn.commit()
    flash(f"Deleted CV #{cand_id}.", "success")
    return redirect(url_for("index"))


@app.get("/admin/users")
@admin_required
def admin_users():
    rows = get_upload_counts()
    return render_template("admin_users.html", rows=rows)


@app.route("/admin/cvs/<path:filename>")
@admin_required
def admin_download_cv(filename):
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)


@app.post("/admin/users/<int:uid>/deactivate")
@admin_required
def deactivate_user(uid: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET active=0 WHERE id=?", (uid,))
        conn.commit()
    flash(f"User #{uid} deactivated.", "success")
    return redirect(url_for("admin_users"))


@app.post("/admin/users/<int:uid>/activate")
@admin_required
def activate_user(uid: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE users SET active=1 WHERE id=?", (uid,))
        conn.commit()
    flash(f"User #{uid} activated.", "success")
    return redirect(url_for("admin_users"))


@app.post("/admin/users/<int:uid>/reset")
@admin_required
def admin_reset_user(uid: int):
    token = secrets.token_urlsafe(24)
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO reset_tokens (user_id, token, expires_at) VALUES (?,?,?)",
            (uid, token, expires),
        )
        conn.commit()
    flash(f"Reset link: {url_for('reset_form', token=token, _external=False)}", "info")
    return redirect(url_for("admin_users"))

@app.get("/healthz")
def healthz():
    return "ok", 200

init_db()
if __name__ == "__main__":

    app.run(debug=False)
