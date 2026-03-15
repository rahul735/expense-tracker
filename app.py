from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB = "expenses.db"


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL
            )
        """)


@app.route("/")
def index():
    with get_db() as conn:
        expenses = conn.execute("SELECT * FROM expenses ORDER BY date DESC").fetchall()
        summary = conn.execute("""
            SELECT strftime('%Y-%m', date) as month, category, SUM(amount) as total
            FROM expenses
            GROUP BY month, category
            ORDER BY month DESC
        """).fetchall()
    return render_template("index.html", expenses=expenses, summary=summary)


@app.route("/add", methods=["POST"])
def add():
    date = request.form["date"]
    category = request.form["category"]
    description = request.form["description"]
    amount = float(request.form["amount"])
    with get_db() as conn:
        conn.execute(
            "INSERT INTO expenses (date, category, description, amount) VALUES (?, ?, ?, ?)",
            (date, category, description, amount),
        )
    return redirect(url_for("index"))


@app.route("/delete/<int:expense_id>")
def delete(expense_id):
    with get_db() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
