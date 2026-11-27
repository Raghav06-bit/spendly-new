import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize database on startup
with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Validate required fields
        if not name or not email or not password:
            return render_template("register.html", error="All fields are required.")

        # Validate password length
        if len(password) < 8:
            return render_template(
                "register.html",
                error="Password must be at least 8 characters long.",
            )

        # Check if email already exists
        conn = get_db()
        try:
            existing = conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()

            if existing:
                return render_template(
                    "register.html",
                    error="Email address is already registered.",
                )

            # Insert new user with hashed password
            password_hash = generate_password_hash(password)
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, password_hash),
            )
            conn.commit()
            user_id = cursor.lastrowid

            # Log in via session
            session["user_id"] = user_id
            session["user_name"] = name

            flash("Registration successful! Welcome to Spendly.", "success")
            return redirect(url_for("profile"))
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Validate required fields
        if not email or not password:
            return render_template(
                "login.html",
                error="All fields are required.",
                email=email,
            )

        # Look up user by email (emails stored lowercase)
        conn = get_db()
        try:
            user = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()

            if not user or not check_password_hash(user["password_hash"], password):
                return render_template(
                    "login.html",
                    error="Invalid email or password.",
                    email=email,
                )

            # Log in via session
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("profile"))
        finally:
            conn.close()

    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if "user_id" not in session:
        flash("Please sign in to view your profile.", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # Get user info from database
    user_info = get_user_by_id(user_id)
    if not user_info:
        flash("User not found.", "error")
        return redirect(url_for("login"))

    # Get summary stats
    summary = get_summary_stats(user_id)

    # Get recent transactions (limit 10)
    recent_transactions = get_recent_transactions(user_id, limit=10)

    # Get category breakdown
    category_breakdown = get_category_breakdown(user_id)

    # Format stats for template
    stats = [
        ("Total spent", f"₹{summary['total_spent']:,.2f}", "All time"),
        ("Transactions", str(summary['transaction_count']), "All time"),
        ("Top category", summary['top_category'], f"₹{summary['top_category_amount']:,.2f} spent" if summary['top_category'] != "—" else "No expenses yet"),
    ]

    # Format transactions for template (date in DD Mon format)
    transactions = []
    for t in recent_transactions:
        try:
            dt = datetime.fromisoformat(t["date"])
            date_str = dt.strftime("%d %b")
        except ValueError:
            date_str = t["date"]
        transactions.append((
            date_str,
            t["description"],
            t["category"],
            f"{t['amount']:.2f}"
        ))

    # Format categories for template
    categories = [
        (cat["name"], f"{cat['amount']:.2f}")
        for cat in category_breakdown
    ]

    return render_template(
        "profile.html",
        profile=user_info,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
