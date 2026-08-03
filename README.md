# Success People Parish

A simple full-stack portal (Flask + SQLite) where members can log in to view
their profile and results, and an admin can add/edit members and enter results.

## Features
- Admin login: add, edit, delete members
- Admin: add results per member (score auto-converted to a letter grade)
- Member login: view own profile and results only
- SQLite database (auto-created on first run, no setup needed)

## Requirements
- Python 3.9+
- Flask (`pip install flask`)

## Setup & Run

```bash
cd portal
pip install flask
python3 app.py
```

Then open **http://localhost:5000** in your browser.

The database (`portal.db`) is created automatically the first time you run the
app, seeded with a demo admin and a demo member so you can log in right away.

## Demo accounts

| Role   | Username | Password  |
|--------|----------|-----------|
| Admin  | admin    | admin123  |
| Member | MEM001   | member123 |

**Change these before using this for anything real** — edit the seed data in
`init_db()` inside `app.py`, or just log in as admin and manage members from
the dashboard, then delete the demo accounts directly from the database.

## Project structure

```
portal/
├── app.py                  # Flask app: routes, DB setup, auth
├── portal.db                # SQLite database (auto-created)
├── templates/               # Jinja2 HTML templates
└── static/css/style.css     # Styling
```

## Notes on going further
- Passwords are hashed with Werkzeug's `generate_password_hash` — good for a
  demo, but for production add HTTPS, stronger secret key management, and
  rate-limiting on login.
- `app.secret_key` in `app.py` is a placeholder — replace it with a random
  secret before deploying anywhere public.
- To deploy for real use, host it with something like Gunicorn behind Nginx,
  or a PaaS (Render, Railway, PythonAnywhere) rather than Flask's built-in
  dev server.
