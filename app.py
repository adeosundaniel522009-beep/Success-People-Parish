import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "portal.db")

app = Flask(__name__)
app.secret_key = "change-this-secret-key-in-production"


# ---------- Database helpers ----------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    fresh = not os.path.exists(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'member'))
        );

        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            member_no TEXT UNIQUE NOT NULL,
            department TEXT,
            level TEXT,
            email TEXT,
            phone TEXT,
            photo_url TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL,
            session TEXT NOT NULL,
            semester TEXT NOT NULL,
            course_code TEXT NOT NULL,
            course_title TEXT,
            score REAL NOT NULL,
            grade TEXT,
            FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE
        );
        """
    )
    db.commit()

    if fresh:
        # seed a default admin and one demo member so the app is usable immediately
        admin_hash = generate_password_hash("admin123")
        db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
            ("admin", admin_hash),
        )

        member_hash = generate_password_hash("member123")
        cur = db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'member')",
            ("MEM001", member_hash),
        )
        user_id = cur.lastrowid
        cur2 = db.execute(
            """INSERT INTO members (user_id, full_name, member_no, department, level, email, phone)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, "Ada Okafor", "MEM001", "Computer Science", "300", "ada@example.com", "08000000000"),
        )
        member_id = cur2.lastrowid
        db.execute(
            """INSERT INTO results (member_id, session, semester, course_code, course_title, score, grade)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (member_id, "2024/2025", "First", "CSC301", "Data Structures", 78, "A"),
        )
        db.execute(
            """INSERT INTO results (member_id, session, semester, course_code, course_title, score, grade)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (member_id, "2024/2025", "First", "CSC305", "Operating Systems", 64, "C"),
        )
        db.commit()
    db.close()


def grade_from_score(score):
    score = float(score)
    if score >= 70:
        return "A"
    if score >= 60:
        return "B"
    if score >= 50:
        return "C"
    if score >= 45:
        return "D"
    if score >= 40:
        return "E"
    return "F"


# ---------- Auth helpers ----------

def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("You do not have access to that page.", "error")
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


# ---------- Public / Auth routes ----------

@app.route("/")
def index():
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("member_dashboard"))
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["username"] = user["username"]
            flash(f"Welcome back, {username}!", "success")
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("member_dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


# ---------- Member routes ----------

@app.route("/member/dashboard")
@login_required(role="member")
def member_dashboard():
    db = get_db()
    member = db.execute(
        "SELECT * FROM members WHERE user_id = ?", (session["user_id"],)
    ).fetchone()
    results = db.execute(
        "SELECT * FROM results WHERE member_id = ? ORDER BY session, semester, course_code",
        (member["id"],),
    ).fetchall()
    return render_template("member_dashboard.html", member=member, results=results)


# ---------- Admin routes ----------

@app.route("/admin/dashboard")
@login_required(role="admin")
def admin_dashboard():
    db = get_db()
    member_count = db.execute("SELECT COUNT(*) AS c FROM members").fetchone()["c"]
    result_count = db.execute("SELECT COUNT(*) AS c FROM results").fetchone()["c"]
    recent_members = db.execute(
        "SELECT * FROM members ORDER BY id DESC LIMIT 5"
    ).fetchall()
    return render_template(
        "admin_dashboard.html",
        member_count=member_count,
        result_count=result_count,
        recent_members=recent_members,
    )


@app.route("/admin/members")
@login_required(role="admin")
def admin_members():
    db = get_db()
    q = request.args.get("q", "").strip()
    if q:
        members = db.execute(
            """SELECT * FROM members
               WHERE full_name LIKE ? OR member_no LIKE ? OR department LIKE ?
               ORDER BY full_name""",
            (f"%{q}%", f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        members = db.execute("SELECT * FROM members ORDER BY full_name").fetchall()
    return render_template("admin_members.html", members=members, q=q)


@app.route("/admin/members/new", methods=["GET", "POST"])
@login_required(role="admin")
def admin_member_new():
    if request.method == "POST":
        db = get_db()
        full_name = request.form.get("full_name", "").strip()
        member_no = request.form.get("member_no", "").strip()
        department = request.form.get("department", "").strip()
        level = request.form.get("level", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip() or "member123"

        if not full_name or not member_no:
            flash("Full name and member number are required.", "error")
            return render_template("admin_member_form.html", member=None)

        existing = db.execute(
            "SELECT id FROM users WHERE username = ?", (member_no,)
        ).fetchone()
        if existing:
            flash("A member with that member number already exists.", "error")
            return render_template("admin_member_form.html", member=None)

        cur = db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'member')",
            (member_no, generate_password_hash(password)),
        )
        user_id = cur.lastrowid
        db.execute(
            """INSERT INTO members (user_id, full_name, member_no, department, level, email, phone)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, full_name, member_no, department, level, email, phone),
        )
        db.commit()
        flash(f"Member added. Login: {member_no} / {password}", "success")
        return redirect(url_for("admin_members"))
    return render_template("admin_member_form.html", member=None)


@app.route("/admin/members/<int:member_id>/edit", methods=["GET", "POST"])
@login_required(role="admin")
def admin_member_edit(member_id):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if not member:
        flash("Member not found.", "error")
        return redirect(url_for("admin_members"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        department = request.form.get("department", "").strip()
        level = request.form.get("level", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        db.execute(
            """UPDATE members SET full_name=?, department=?, level=?, email=?, phone=?
               WHERE id=?""",
            (full_name, department, level, email, phone, member_id),
        )
        db.commit()
        flash("Member updated.", "success")
        return redirect(url_for("admin_members"))

    return render_template("admin_member_form.html", member=member)


@app.route("/admin/members/<int:member_id>/delete", methods=["POST"])
@login_required(role="admin")
def admin_member_delete(member_id):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if member:
        db.execute("DELETE FROM users WHERE id = ?", (member["user_id"],))
        db.execute("DELETE FROM members WHERE id = ?", (member_id,))
        db.commit()
        flash("Member removed.", "success")
    return redirect(url_for("admin_members"))


@app.route("/admin/members/<int:member_id>/results", methods=["GET", "POST"])
@login_required(role="admin")
def admin_member_results(member_id):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if not member:
        flash("Member not found.", "error")
        return redirect(url_for("admin_members"))

    if request.method == "POST":
        session_ = request.form.get("session", "").strip()
        semester = request.form.get("semester", "").strip()
        course_code = request.form.get("course_code", "").strip().upper()
        course_title = request.form.get("course_title", "").strip()
        score = request.form.get("score", "").strip()

        try:
            score_val = float(score)
            if not (0 <= score_val <= 100):
                raise ValueError
        except ValueError:
            flash("Score must be a number between 0 and 100.", "error")
            return redirect(url_for("admin_member_results", member_id=member_id))

        grade = grade_from_score(score_val)
        db.execute(
            """INSERT INTO results (member_id, session, semester, course_code, course_title, score, grade)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (member_id, session_, semester, course_code, course_title, score_val, grade),
        )
        db.commit()
        flash("Result added.", "success")
        return redirect(url_for("admin_member_results", member_id=member_id))

    results = db.execute(
        "SELECT * FROM results WHERE member_id = ? ORDER BY session, semester, course_code",
        (member_id,),
    ).fetchall()
    return render_template("admin_results.html", member=member, results=results)


@app.route("/admin/results/<int:result_id>/delete", methods=["POST"])
@login_required(role="admin")
def admin_result_delete(result_id):
    db = get_db()
    row = db.execute("SELECT member_id FROM results WHERE id = ?", (result_id,)).fetchone()
    db.execute("DELETE FROM results WHERE id = ?", (result_id,))
    db.commit()
    flash("Result removed.", "success")
    if row:
        return redirect(url_for("admin_member_results", member_id=row["member_id"]))
    return redirect(url_for("admin_members"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
