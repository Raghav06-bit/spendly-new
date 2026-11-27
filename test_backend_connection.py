import pytest
import os
from datetime import datetime
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.secret_key = "test-secret-key"
    if os.path.exists("spendly.db"):
        os.remove("spendly.db")
    with app.test_client() as client:
        with app.app_context():
            from database.db import init_db, seed_db
            init_db()
            seed_db()
        yield client


@pytest.fixture
def db_app():
    """App context with initialized database."""
    app.config["TESTING"] = True
    if os.path.exists("spendly.db"):
        os.remove("spendly.db")
    with app.app_context():
        from database.db import init_db, seed_db
        init_db()
        seed_db()
        yield app


# Unit tests for query helpers

def test_get_user_by_id_valid(db_app):
    """Valid user_id returns dict with name, email, member_since."""
    with db_app.app_context():
        from database.queries import get_user_by_id
        user = get_user_by_id(1)
        assert user is not None
        assert user["name"] == "Demo User"
        assert user["email"] == "demo@spendly.com"
        assert user["member_since"] is not None


def test_get_user_by_id_nonexistent(db_app):
    """Non-existent user_id returns None."""
    with db_app.app_context():
        from database.queries import get_user_by_id
        user = get_user_by_id(999)
        assert user is None


def test_get_summary_stats_with_expenses(db_app):
    """User with expenses returns correct totals."""
    with db_app.app_context():
        from database.queries import get_summary_stats
        stats = get_summary_stats(1)
        # Seed data amounts: 45.50 + 22.00 + 120.00 + 35.00 + 55.00 + 89.99 + 15.00 + 30.00 = 412.49
        assert stats["total_spent"] == 412.49
        assert stats["transaction_count"] == 8
        assert stats["top_category"] == "Bills"


def test_get_summary_stats_no_expenses(db_app):
    """User with no expenses returns zeros."""
    with db_app.app_context():
        from database.db import get_db
        from werkzeug.security import generate_password_hash
        conn = get_db()
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("New User", "new@example.com", generate_password_hash("password123"))
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        from database.queries import get_summary_stats
        stats = get_summary_stats(user_id)
        assert stats["total_spent"] == 0
        assert stats["transaction_count"] == 0
        assert stats["top_category"] == "—"


def test_get_recent_transactions_with_expenses(db_app):
    """User with expenses returns list ordered newest-first."""
    with db_app.app_context():
        from database.queries import get_recent_transactions
        transactions = get_recent_transactions(1, limit=10)
        assert len(transactions) == 8
        # Check newest first (date DESC)
        assert transactions[0]["date"] >= transactions[-1]["date"]
        # Check each has required fields
        for t in transactions:
            assert "date" in t
            assert "description" in t
            assert "category" in t
            assert "amount" in t


def test_get_recent_transactions_no_expenses(db_app):
    """User with no expenses returns empty list."""
    with db_app.app_context():
        from database.db import get_db
        from werkzeug.security import generate_password_hash
        conn = get_db()
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("New User", "new2@example.com", generate_password_hash("password123"))
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        from database.queries import get_recent_transactions
        transactions = get_recent_transactions(user_id)
        assert transactions == []


def test_get_category_breakdown_with_expenses(db_app):
    """User with expenses returns categories ordered by amount desc with pct summing to 100."""
    with db_app.app_context():
        from database.queries import get_category_breakdown
        breakdown = get_category_breakdown(1)
        assert len(breakdown) == 7  # 7 categories in seed data
        # Ordered by amount desc
        amounts = [c["amount"] for c in breakdown]
        assert amounts == sorted(amounts, reverse=True)
        # pct are integers summing to 100
        total_pct = sum(c["pct"] for c in breakdown)
        assert total_pct == 100
        for c in breakdown:
            assert isinstance(c["pct"], int)


def test_get_category_breakdown_no_expenses(db_app):
    """User with no expenses returns empty list."""
    with db_app.app_context():
        from database.db import get_db
        from werkzeug.security import generate_password_hash
        conn = get_db()
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("New User", "new3@example.com", generate_password_hash("password123"))
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        from database.queries import get_category_breakdown
        breakdown = get_category_breakdown(user_id)
        assert breakdown == []


# Route tests

def test_profile_unauthenticated_redirects_to_login(client):
    """GET /profile without session redirects to /login."""
    response = client.get("/profile", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")


def test_profile_authenticated_seed_user(client):
    """GET /profile with seed user shows correct data."""
    # Login as seed user
    client.post("/login", data={
        "email": "demo@spendly.com",
        "password": "demo123"
    }, follow_redirects=False)

    response = client.get("/profile")
    assert response.status_code == 200
    assert b"Demo User" in response.data
    assert b"demo@spendly.com" in response.data
    assert b"\xe2\x82\xb9" in response.data  # ₹ symbol

    # Total spent = 412.49 (sum of seed expenses)
    assert b"412.49" in response.data
    # Transaction count = 8
    assert b"8" in response.data
    # Top category = Bills
    assert b"Bills" in response.data

    # Transaction list appears (8 rows)
    assert response.data.count(b"<tr>") >= 8

    # Category breakdown contains all 7 categories
    categories = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
    for cat in categories:
        assert cat.encode() in response.data


def test_profile_new_user_shows_empty_state(client):
    """New user profile shows zero totals and empty breakdown."""
    # Register and login new user
    client.post("/register", data={
        "name": "New User",
        "email": "newuser@example.com",
        "password": "password123"
    }, follow_redirects=False)

    response = client.get("/profile")
    assert response.status_code == 200
    assert b"New User" in response.data
    assert b"0.00" in response.data or b"0" in response.data
    # Should not crash - no errors
    assert b"Error" not in response.data or b"error" not in response.data.lower()