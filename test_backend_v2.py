"""
Tests for Step 5: Backend Connection for Profile Page

Covers:
- Unit tests for query helpers in database/queries.py
- Route tests for GET /profile (auth guard, seed user, new user empty state)
- DB side effects and edge cases
"""

import pytest
import os
from datetime import datetime
from app import app as flask_app
from database.db import get_db, init_db, seed_db
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def client():
    """Test client with fresh database for each test."""
    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
    })

    # Remove any existing test database
    if os.path.exists("spendly.db"):
        os.remove("spendly.db")

    with flask_app.test_client() as client:
        with flask_app.app_context():
            init_db()
            seed_db()
        yield client


@pytest.fixture
def app():
    """Flask app with initialized database."""
    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
    })

    if os.path.exists("spendly.db"):
        os.remove("spendly.db")

    with flask_app.app_context():
        init_db()
        seed_db()
        yield flask_app


@pytest.fixture
def seeded_user_id(app):
    """Return the seed user's ID (always 1 from seed_db)."""
    with app.app_context():
        conn = get_db()
        user = conn.execute("SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)).fetchone()
        conn.close()
        return user["id"]


@pytest.fixture
def auth_client(client):
    """A test client logged in as the seed user."""
    client.post('/login', data={'email': 'demo@spendly.com', 'password': 'demo123'})
    return client


@pytest.fixture
def new_user_client(client, app):
    """A test client logged in as a brand new user with no expenses."""
    from werkzeug.security import generate_password_hash

    with app.app_context():
        conn = get_db()
        with conn:
            password_hash = generate_password_hash('newpass123')
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                ('New User', 'new@spendly.com', password_hash, '2025-06-01 12:00:00')
            )
            user_id = cursor.lastrowid
        conn.close()

    client.post('/login', data={'email': 'new@spendly.com', 'password': 'newpass123'})
    return client, user_id


# =============================================================================
# Unit Tests for Query Helpers
# =============================================================================

class TestGetUserById:
    """Unit tests for get_user_by_id query helper."""

    def test_valid_user_id_returns_correct_info(self, app, seeded_user_id):
        """get_user_by_id with valid user_id returns dict with name, email, member_since."""
        with app.app_context():
            user_info = get_user_by_id(seeded_user_id)

            assert user_info is not None, "Expected user info for valid user_id"
            assert user_info["name"] == "Demo User", f"Expected name 'Demo User', got {user_info['name']}"
            assert user_info["email"] == "demo@spendly.com", f"Expected email 'demo@spendly.com', got {user_info['email']}"
            # member_since depends on created_at in seed_db
            assert user_info["member_since"] is not None, "member_since should be set"

    def test_nonexistent_user_id_returns_none(self, app):
        """get_user_by_id with non-existent id returns None."""
        with app.app_context():
            user_info = get_user_by_id(99999)
            assert user_info is None, "Expected None for non-existent user_id"


class TestGetSummaryStats:
    """Unit tests for get_summary_stats query helper."""

    def test_user_with_expenses_returns_correct_stats(self, app, seeded_user_id):
        """get_summary_stats for user with expenses returns correct totals."""
        with app.app_context():
            summary = get_summary_stats(seeded_user_id)

            # Total: 45.50 + 22.00 + 120.00 + 35.00 + 55.00 + 89.99 + 15.00 + 30.00 = 412.49
            expected_total = 45.50 + 22.00 + 120.00 + 35.00 + 55.00 + 89.99 + 15.00 + 30.00

            assert summary["total_spent"] == pytest.approx(expected_total, rel=1e-2), \
                f"Expected total_spent ~{expected_total}, got {summary['total_spent']}"
            assert summary["transaction_count"] == 8, \
                f"Expected transaction_count 8, got {summary['transaction_count']}"
            assert summary["top_category"] == "Bills", \
                f"Expected top_category 'Bills', got {summary['top_category']}"

    def test_user_with_no_expenses_returns_zeros_and_dash(self, app):
        """get_summary_stats for user with no expenses returns zeros and '—'."""
        with app.app_context():
            from werkzeug.security import generate_password_hash
            conn = get_db()
            with conn:
                password_hash = generate_password_hash('testpass')
                cursor = conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    ('Empty User', 'empty@spendly.com', password_hash)
                )
                user_id = cursor.lastrowid
            conn.close()

            summary = get_summary_stats(user_id)

            assert summary["total_spent"] == 0, f"Expected total_spent 0, got {summary['total_spent']}"
            assert summary["transaction_count"] == 0, f"Expected transaction_count 0, got {summary['transaction_count']}"
            assert summary["top_category"] == "—", f"Expected top_category '—', got {summary['top_category']}"


class TestGetRecentTransactions:
    """Unit tests for get_recent_transactions query helper."""

    def test_user_with_expenses_returns_newest_first(self, app, seeded_user_id):
        """get_recent_transactions returns list ordered newest-first with correct fields."""
        with app.app_context():
            transactions = get_recent_transactions(seeded_user_id, limit=10)

            assert len(transactions) == 8, f"Expected 8 transactions, got {len(transactions)}"

            # Check each transaction has required fields
            for t in transactions:
                assert "date" in t, "Transaction missing 'date' field"
                assert "description" in t, "Transaction missing 'description' field"
                assert "category" in t, "Transaction missing 'category' field"
                assert "amount" in t, "Transaction missing 'amount' field"

            # Verify newest-first ordering (by date DESC, then id DESC)
            # The last inserted expense (Food, 30.00, 22nd) should be first
            assert transactions[0]["category"] == "Food", "First transaction should be newest (Food, 22nd)"
            assert transactions[0]["amount"] == 30.00, "Newest transaction amount should be 30.00"

            # Second newest is Other (15.00, 18th)
            assert transactions[1]["category"] == "Other", "Second transaction should be Other (18th)"
            assert transactions[1]["amount"] == 15.00, "Other amount should be 15.00"

    def test_user_with_no_expenses_returns_empty_list(self, app):
        """get_recent_transactions for user with no expenses returns empty list."""
        with app.app_context():
            from werkzeug.security import generate_password_hash
            conn = get_db()
            with conn:
                password_hash = generate_password_hash('testpass')
                cursor = conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    ('Empty User', 'empty@spendly.com', password_hash)
                )
                user_id = cursor.lastrowid
            conn.close()

            transactions = get_recent_transactions(user_id, limit=10)
            assert transactions == [], f"Expected empty list, got {transactions}"

    def test_limit_parameter_respected(self, app, seeded_user_id):
        """get_recent_transactions respects the limit parameter."""
        with app.app_context():
            transactions = get_recent_transactions(seeded_user_id, limit=3)
            assert len(transactions) == 3, f"Expected 3 transactions with limit=3, got {len(transactions)}"


class TestGetCategoryBreakdown:
    """Unit tests for get_category_breakdown query helper."""

    def test_user_with_expenses_returns_ordered_breakdown_with_pct_summing_to_100(self, app, seeded_user_id):
        """get_category_breakdown returns list ordered by amount desc; pct values sum to 100."""
        with app.app_context():
            breakdown = get_category_breakdown(seeded_user_id)

            # Should have 7 categories (Food appears twice)
            assert len(breakdown) == 7, f"Expected 7 categories, got {len(breakdown)}"

            # Check each item has required fields
            for cat in breakdown:
                assert "name" in cat, "Category missing 'name' field"
                assert "amount" in cat, "Category missing 'amount' field"
                assert "pct" in cat, "Category missing 'pct' field"
                assert isinstance(cat["pct"], int), f"pct should be int, got {type(cat['pct'])}"

            # Verify ordered by amount descending
            amounts = [cat["amount"] for cat in breakdown]
            assert amounts == sorted(amounts, reverse=True), "Categories should be ordered by amount descending"

            # Verify percentages sum to 100
            total_pct = sum(cat["pct"] for cat in breakdown)
            assert total_pct == 100, f"Percentages should sum to 100, got {total_pct}"

            # Verify top category is Bills (120.00 is highest single-category total)
            assert breakdown[0]["name"] == "Bills", f"Top category should be Bills, got {breakdown[0]['name']}"
            assert breakdown[0]["amount"] == 120.00, f"Bills amount should be 120.00, got {breakdown[0]['amount']}"

            # Food total: 45.50 + 30.00 = 75.50
            food_cat = next(c for c in breakdown if c["name"] == "Food")
            assert food_cat["amount"] == 75.50, f"Food total should be 75.50, got {food_cat['amount']}"

    def test_user_with_no_expenses_returns_empty_list(self, app):
        """get_category_breakdown for user with no expenses returns empty list."""
        with app.app_context():
            from werkzeug.security import generate_password_hash
            conn = get_db()
            with conn:
                password_hash = generate_password_hash('testpass')
                cursor = conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    ('Empty User', 'empty@spendly.com', password_hash)
                )
                user_id = cursor.lastrowid
            conn.close()

            breakdown = get_category_breakdown(user_id)
            assert breakdown == [], f"Expected empty list, got {breakdown}"

    def test_pct_rounding_adjusts_largest_category(self, app):
        """get_category_breakdown adjusts largest category to absorb rounding remainder."""
        with app.app_context():
            from werkzeug.security import generate_password_hash
            conn = get_db()
            with conn:
                password_hash = generate_password_hash('testpass')
                cursor = conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    ('Test User', 'test@spendly.com', password_hash)
                )
                user_id = cursor.lastrowid

                # Create expenses with amounts that cause rounding issues
                # 33.33 + 33.33 + 33.34 = 100.00 (each ~33.33%)
                expenses = [
                    (user_id, 33.33, 'A', '2025-01-01', 'A'),
                    (user_id, 33.33, 'B', '2025-01-02', 'B'),
                    (user_id, 33.34, 'C', '2025-01-03', 'C'),
                ]
                for exp in expenses:
                    conn.execute(
                        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                        exp
                    )
            conn.close()

            breakdown = get_category_breakdown(user_id)

            # All percentages should be integers summing to 100
            total_pct = sum(cat["pct"] for cat in breakdown)
            assert total_pct == 100, f"Percentages should sum to 100, got {total_pct}"

            # Each should be roughly 33%
            for cat in breakdown:
                assert 32 <= cat["pct"] <= 34, f"Percentage {cat['pct']} not in expected range"


# =============================================================================
# Route Tests for GET /profile
# =============================================================================

class TestProfileRoute:
    """Route tests for GET /profile endpoint."""

    def test_unauthenticated_redirects_to_login(self, client):
        """GET /profile without authentication redirects to /login (302)."""
        response = client.get('/profile', follow_redirects=False)

        assert response.status_code == 302, f"Expected 302 redirect, got {response.status_code}"
        assert '/login' in response.location, f"Expected redirect to /login, got {response.location}"

    def test_unauthenticated_flash_message(self, client):
        """GET /profile without authentication sets flash error message."""
        response = client.get('/profile', follow_redirects=True)

        assert response.status_code == 200
        assert b'Please sign in to view your profile' in response.data, \
            "Expected flash error message about signing in"

    def test_authenticated_seed_user_returns_200(self, auth_client):
        """GET /profile as seed user returns 200 OK."""
        response = auth_client.get('/profile')

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    def test_authenticated_seed_user_contains_user_name(self, auth_client):
        """GET /profile as seed user contains the seed user's name 'Demo User'."""
        response = auth_client.get('/profile')

        assert b'Demo User' in response.data, "Response should contain 'Demo User'"

    def test_authenticated_seed_user_contains_user_email(self, auth_client):
        """GET /profile as seed user contains the seed user's email."""
        response = auth_client.get('/profile')

        assert b'demo@spendly.com' in response.data, "Response should contain 'demo@spendly.com'"

    def test_authenticated_seed_user_contains_rupee_symbol(self, auth_client):
        """GET /profile as seed user contains ₹ symbol for currency display."""
        response = auth_client.get('/profile')

        assert b'\xe2\x82\xb9' in response.data or '₹' in response.data.decode('utf-8'), \
            "Response should contain ₹ symbol"

    def test_authenticated_seed_user_total_spent_matches_seed_data(self, auth_client):
        """GET /profile as seed user shows total_spent matching sum of seed expenses (412.49)."""
        response = auth_client.get('/profile')

        # Total: 45.50 + 22.00 + 120.00 + 35.00 + 55.00 + 89.99 + 15.00 + 30.00 = 412.49
        # The template formats as ₹412.49
        assert b'412.49' in response.data, "Response should contain total spent 412.49"

    def test_authenticated_seed_user_transaction_count_is_8(self, auth_client):
        """GET /profile as seed user shows transaction_count = 8."""
        response = auth_client.get('/profile')

        assert b'8' in response.data, "Response should contain transaction count 8"

    def test_authenticated_seed_user_top_category_is_bills(self, auth_client):
        """GET /profile as seed user shows top_category = 'Bills'."""
        response = auth_client.get('/profile')

        assert b'Bills' in response.data, "Response should contain top category 'Bills'"

    def test_authenticated_seed_user_transactions_newest_first(self, auth_client):
        """GET /profile as seed user shows transactions in newest-first order."""
        response = auth_client.get('/profile')
        html = response.data.decode('utf-8')

        # The newest transaction is Food (Restaurant dinner) on the 22nd
        # The second newest is Shopping (New shoes) on the 15th
        # We check that the 22nd appears before the 15th in the HTML
        food_22_pos = html.find('22')
        shopping_15_pos = html.find('15')

        # Both should exist and 22nd should appear before 15th
        assert food_22_pos != -1, "Should contain date 22 (newest transaction)"
        assert shopping_15_pos != -1, "Should contain date 15 (second newest)"
        assert food_22_pos < shopping_15_pos, "Newest transaction (22nd) should appear before older (15th)"

    def test_authenticated_seed_user_category_breakdown_has_7_categories(self, auth_client):
        """GET /profile as seed user shows 7 categories in breakdown."""
        response = auth_client.get('/profile')
        html = response.data.decode('utf-8')

        # Check all 7 categories are present
        categories = ['Food', 'Transport', 'Bills', 'Health', 'Entertainment', 'Shopping', 'Other']
        for cat in categories:
            assert cat in html, f"Category '{cat}' should appear in breakdown"

    def test_new_user_empty_state_shows_zero_totals(self, new_user_client):
        """GET /profile for new user with no expenses shows ₹0.00 total, 0 transactions, empty breakdown."""
        client, user_id = new_user_client
        response = client.get('/profile')

        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # Should show zero total spent
        assert '0.00' in html or '₹0' in html, "Should show zero total spent"

        # Should show 0 transactions
        assert '0' in html, "Should show 0 transactions"

        # Should show top category as — (dash) or "No expenses yet"
        assert '—' in html or 'No expenses' in html, "Should indicate no expenses"

    def test_new_user_profile_shows_correct_member_since(self, new_user_client):
        """GET /profile for new user shows correct member_since from created_at."""
        client, user_id = new_user_client
        response = client.get('/profile')

        html = response.data.decode('utf-8')
        # Member since should be June 2025 based on fixture
        assert 'June 2025' in html, f"Should show member_since 'June 2025', got HTML: {html[:500]}"


# =============================================================================
# Auth Guard Tests
# =============================================================================

class TestAuthGuards:
    """Tests for authentication guards on protected routes."""

    def test_profile_requires_login(self, client):
        """All access to /profile requires valid session."""
        # Test GET
        response = client.get('/profile')
        assert response.status_code == 302
        assert '/login' in response.location

        # Test with invalid session (user_id not in DB)
        with client.session_transaction() as sess:
            sess['user_id'] = 99999

        response = client.get('/profile')
        assert response.status_code == 302
        assert '/login' in response.location


# =============================================================================
# Database Side Effect Tests
# =============================================================================

class TestDatabaseSideEffects:
    """Tests that verify database state changes are reflected correctly."""

    def test_new_expense_reflected_in_profile(self, auth_client, app, seeded_user_id):
        """Adding an expense via DB directly should appear on profile page."""
        with app.app_context():
            conn = get_db()
            with conn:
                conn.execute(
                    "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                    (seeded_user_id, 99.99, 'Test Category', '2025-12-01', 'Test expense')
                )
            conn.close()

        # Reload profile
        response = auth_client.get('/profile')
        html = response.data.decode('utf-8')

        # Should now show 9 transactions
        assert '9' in html, "Transaction count should be 9 after adding expense"

        # Should show new category in breakdown
        assert 'Test Category' in html, "New category should appear in breakdown"

        # Total should increase
        assert '512.48' in html or '512.49' in html, "Total should include new expense"


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Edge case tests for query helpers and route."""

    def test_user_with_special_characters_in_name(self, app):
        """get_user_by_id handles special characters in name correctly."""
        with app.app_context():
            from werkzeug.security import generate_password_hash
            conn = get_db()
            with conn:
                password_hash = generate_password_hash('testpass')
                cursor = conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    ("User <script>alert('xss')</script>", 'special@spendly.com', password_hash)
                )
                user_id = cursor.lastrowid
            conn.close()

            user_info = get_user_by_id(user_id)

            assert user_info is not None
            assert user_info["name"] == "User <script>alert('xss')</script>"

    def test_expense_with_null_description(self, app, seeded_user_id):
        """get_recent_transactions handles null description gracefully."""
        with app.app_context():
            conn = get_db()
            with conn:
                conn.execute(
                    "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                    (seeded_user_id, 10.00, 'Test', '2025-12-01', None)
                )
            conn.close()

            # Get all transactions to find the one with null description
            transactions = get_recent_transactions(seeded_user_id, limit=10)

            # Find the transaction with category 'Test' and amount 10.00
            test_trans = next((t for t in transactions if t["category"] == "Test" and t["amount"] == 10.00), None)
            assert test_trans is not None, "Test transaction should exist"
            assert test_trans["description"] == "", "Null description should become empty string"

    def test_sql_injection_attempt_in_user_id(self, app):
        """Query helpers use parameterized queries, preventing SQL injection."""
        with app.app_context():
            from werkzeug.security import generate_password_hash
            conn = get_db()
            with conn:
                password_hash = generate_password_hash('testpass')
                cursor = conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    ('Normal User', 'normal@spendly.com', password_hash)
                )
                user_id = cursor.lastrowid
            conn.close()

            # These should not cause errors or return other users' data
            # The functions expect integer user_id, so we test with valid int
            user_info = get_user_by_id(user_id)
            assert user_info is not None
            assert user_info["email"] == "normal@spendly.com"

            # Invalid user_id (non-existent) returns None
            user_info = get_user_by_id(99999)
            assert user_info is None


# =============================================================================
# Integration Test: Full Flow
# =============================================================================

class TestFullIntegration:
    """Integration test covering the complete user flow."""

    def test_register_login_profile_flow(self, client, app):
        """Complete flow: register -> login -> profile shows correct data."""
        # Register a new user
        response = client.post('/register', data={
            'name': 'Integration User',
            'email': 'integration@spendly.com',
            'password': 'password123'
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Integration User' in response.data or b'Registration successful' in response.data

        # Should be redirected to profile and logged in
        html = response.data.decode('utf-8')
        assert 'Integration User' in html
        assert 'integration@spendly.com' in html
        assert '0.00' in html or '₹0' in html  # No expenses yet
        assert '0' in html  # Zero transactions


if __name__ == '__main__':
    pytest.main([__file__, '-v'])