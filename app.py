import os
from flask import Flask, render_template, request, redirect, url_for, jsonify
from sqlalchemy import create_engine, text
from datetime import datetime
from ai_parser import parse_expense_text

app = Flask(__name__)

# Use PostgreSQL on Render (DATABASE_URL env var), SQLite locally
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///expenses.db")

# Render provides postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)


def get_db():
    return engine.connect()


def init_db():
    """Create tables if they don't exist. Called at startup regardless of how app is launched."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS expenses (
                id SERIAL PRIMARY KEY,
                date TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """))
        conn.commit()


def get_setting(key, default=None):
    with get_db() as conn:
        row = conn.execute(text("SELECT value FROM settings WHERE key = :key"), {"key": key}).fetchone()
        return row[0] if row else default


def save_setting(key, value):
    with get_db() as conn:
        conn.execute(text("""
            INSERT INTO settings (key, value) VALUES (:key, :value)
            ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value
        """), {"key": key, "value": value})
        conn.commit()


# ── Main page ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    with get_db() as conn:
        expenses = conn.execute(text("SELECT * FROM expenses ORDER BY date DESC")).fetchall()
        # Use different date formatting for PostgreSQL vs SQLite
        if "postgresql" in DATABASE_URL:
            summary = conn.execute(text("""
                SELECT to_char(date::date, 'YYYY-MM') as month, category, SUM(amount) as total
                FROM expenses
                GROUP BY month, category
                ORDER BY month DESC
            """)).fetchall()
        else:
            summary = conn.execute(text("""
                SELECT strftime('%Y-%m', date) as month, category, SUM(amount) as total
                FROM expenses
                GROUP BY month, category
                ORDER BY month DESC
            """)).fetchall()
    ai_configured = bool(get_setting("api_key"))
    now = datetime.today().strftime("%Y-%m-%d")
    return render_template("index.html", expenses=expenses, summary=summary,
                           ai_configured=ai_configured, now=now)


# ── Manual add ────────────────────────────────────────────────────────────────

@app.route("/add", methods=["POST"])
def add():
    with get_db() as conn:
        conn.execute(text("""
            INSERT INTO expenses (date, category, description, amount)
            VALUES (:date, :category, :description, :amount)
        """), {
            "date": request.form["date"],
            "category": request.form["category"],
            "description": request.form["description"],
            "amount": float(request.form["amount"])
        })
        conn.commit()
    return redirect(url_for("index"))


# ── AI parse (text or voice) ──────────────────────────────────────────────────

@app.route("/parse", methods=["POST"])
def parse():
    text_input = request.json.get("text", "").strip()
    if not text_input:
        return jsonify({"error": "No text provided"}), 400

    provider = get_setting("provider")
    api_key = get_setting("api_key")

    if not provider or not api_key:
        return jsonify({"error": "AI not configured. Please go to Settings and add your API key."}), 400

    result = parse_expense_text(text_input, provider, api_key)
    return jsonify(result)


# ── Save parsed expense ───────────────────────────────────────────────────────

@app.route("/add_parsed", methods=["POST"])
def add_parsed():
    data = request.json
    try:
        with get_db() as conn:
            conn.execute(text("""
                INSERT INTO expenses (date, category, description, amount)
                VALUES (:date, :category, :description, :amount)
            """), {
                "date": data["date"],
                "category": data["category"],
                "description": data.get("description", ""),
                "amount": float(data["amount"])
            })
            conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ── Delete ────────────────────────────────────────────────────────────────────

@app.route("/delete/<int:expense_id>")
def delete(expense_id):
    with get_db() as conn:
        conn.execute(text("DELETE FROM expenses WHERE id = :id"), {"id": expense_id})
        conn.commit()
    return redirect(url_for("index"))


# ── Settings ──────────────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        save_setting("provider", request.form["provider"])
        save_setting("api_key", request.form["api_key"])
        return redirect(url_for("settings"))

    current_provider = get_setting("provider", "gemini")
    raw_key = get_setting("api_key", "")
    masked_key = raw_key[:6] + "****" + raw_key[-4:] if len(raw_key) > 10 else ("****" if raw_key else "")
    return render_template("settings.html", provider=current_provider,
                           masked_key=masked_key, has_key=bool(raw_key))


# Always initialize DB on startup — works with both gunicorn and direct python run
init_db()

if __name__ == "__main__":
    app.run(debug=True)
