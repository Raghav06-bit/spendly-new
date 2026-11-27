"""
Tests for Step 6: Date Filter for Profile Page

Covers:
- Unit tests for query helpers with date_from and date_to filtering
- Route tests for /profile with preset and custom date range filters
- Edge cases: malformed dates, date_from > date_to, empty results
"""

import pytest
import os
from datetime import datetime, timedelta
from app import app as flask_app
from database.db import get_db, init_db, seed_db
from database.queries import (
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)


@pytest.fixture
def client():
    """Test client with fresh database for each test."""
    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
    })

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
def auth_client(client):
    """A test client logged in as the seed user."""
    client.post('/login', data={'email': 'demo@spendly.com', 'password': 'demo123'})
    return client


# =============================================================================
# Unit Tests for Query Helpers with Date Filtering
# =============================================================================

class TestQueryHelpersDateFiltering:
    """Unit tests verifying query helpers correctly filter by date_from and date_to."""

    def test_summary_stats_filtered_by_date_range(self, app):
        """get_summary_stats filters expenses within specified date range."""
        with app.app_context():
            # Seed data dates are in current month YYYY-MM
            current_month = datetime.now().strftime('%Y-%m')

            # Query range covering only days 01 to 10
            date_from = f"{current_month}-01"
            date_to = f"{current_month}-10"

            summary = get_summary_stats(1, date_from=date_from, date_to=date_to)

            # Seed expenses in days 01-10:
            # - Food: 45.50 (02nd)
            # - Transport: 22.00 (05th)
            # - Bills: 120.00 (08th)
            # - Health: 35.00 (10th)
            # Total = 222.50, count = 4
            expected_total = 45.50 + 22.00 + 120.00 + 35.00

            assert summary["total_spent"] == pytest.approx(expected_total, rel=1e-2)
            assert summary["transaction_count"] == 4
            assert summary["top_category"] == "Bills"

    def test_recent_transactions_filtered_by_date_range(self, app):
        """get_recent_transactions returns only items within specified date range."""
        with app.app_context():
            current_month = datetime.now().strftime('%Y-%m')
            date_from = f"{current_month}-01"
            date_to = f"{current_month}-05"

            transactions = get_recent_transactions(1, limit=10, date_from=date_from, date_to=date_to)

            # Should include 05th (Transport, 22.00) and 02nd (Food, 45.50)
            assert len(transactions) == 2
            assert transactions[0]["date"] == f"{current_month}-05"
            assert transactions[1]["date"] == f"{current_month}-02"

    def test_category_breakdown_filtered_by_date_range(self, app):
        """get_category_breakdown returns category totals and percentages within date range."""
        with app.app_context():
            current_month = datetime.now().strftime('%Y-%m')
            date_from = f"{current_month}-01"
            date_to = f"{current_month}-05"

            breakdown = get_category_breakdown(1, date_from=date_from, date_to=date_to)

            # Total = 67.50 (Food 45.50 = 67%, Transport 22.00 = 33%)
            assert len(breakdown) == 2
            total_pct = sum(item["pct"] for item in breakdown)
            assert total_pct == 100

    def test_date_range_no_matching_expenses(self, app):
        """Date range with no matching expenses returns zeros and empty lists."""
        with app.app_context():
            # Query range in distant past
            date_from = "2020-01-01"
            date_to = "2020-01-31"

            summary = get_summary_stats(1, date_from=date_from, date_to=date_to)
            assert summary["total_spent"] == 0
            assert summary["transaction_count"] == 0
            assert summary["top_category"] == "—"

            transactions = get_recent_transactions(1, limit=10, date_from=date_from, date_to=date_to)
            assert transactions == []

            breakdown = get_category_breakdown(1, date_from=date_from, date_to=date_to)
            assert breakdown == []


# =============================================================================
# Route Tests for /profile Date Filtering
# =============================================================================

class TestProfileRouteDateFiltering:
    """Route tests for /profile with preset and custom date filters."""

    def test_profile_no_query_params_returns_unfiltered_data(self, auth_client):
        """GET /profile with no params returns same data as Step 5 (unfiltered)."""
        response = auth_client.get('/profile')
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # All 8 seed transactions present
        assert '412.49' in html
        assert '8' in html
        assert 'Bills' in html

    def test_profile_preset_this_month(self, auth_client):
        """GET /profile?preset=this_month filters data to current month."""
        response = auth_client.get('/profile?preset=this_month')
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # Preset button should be active
        assert 'active' in html
        assert 'This Month' in html

    def test_profile_preset_last_3_months(self, auth_client):
        """GET /profile?preset=last_3_months filters data to last 3 months."""
        response = auth_client.get('/profile?preset=last_3_months')
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        assert 'Last 3 Months' in html

    def test_profile_preset_last_6_months(self, auth_client):
        """GET /profile?preset=last_6_months filters data to last 6 months."""
        response = auth_client.get('/profile?preset=last_6_months')
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        assert 'Last 6 Months' in html

    def test_profile_preset_all_time(self, auth_client):
        """GET /profile?preset=all returns unfiltered data."""
        response = auth_client.get('/profile?preset=all')
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        assert 'All Time' in html
        assert '412.49' in html

    def test_profile_custom_date_range(self, auth_client):
        """GET /profile?date_from=...&date_to=... filters data to custom range."""
        current_month = datetime.now().strftime('%Y-%m')
        date_from = f"{current_month}-01"
        date_to = f"{current_month}-10"

        response = auth_client.get(f'/profile?date_from={date_from}&date_to={date_to}')
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # Check filtered stats: total = 222.50, count = 4
        assert '222.50' in html
        assert '4' in html
        # Pre-filled input fields
        assert f'value="{date_from}"' in html
        assert f'value="{date_to}"' in html

    def test_profile_invalid_date_from_greater_than_date_to(self, auth_client):
        """date_from > date_to shows flash error and falls back to unfiltered."""
        response = auth_client.get('/profile?date_from=2026-12-31&date_to=2026-01-01', follow_redirects=True)
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # Should contain flash error message
        assert 'Start date must be before end date' in html
        # Fallback to unfiltered view (all 8 transactions, total 412.49)
        assert '412.49' in html

    def test_profile_malformed_date_string_silent_fallback(self, auth_client):
        """Malformed date parameter does not crash; silently falls back to unfiltered."""
        response = auth_client.get('/profile?date_from=invalid-date&date_to=not-a-date')
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # Fallback to unfiltered view
        assert '412.49' in html
        assert '8' in html

    def test_profile_empty_results_in_date_range(self, auth_client):
        """Range with no expenses shows ₹0.00 total, 0 transactions, no errors."""
        response = auth_client.get('/profile?date_from=2020-01-01&date_to=2020-01-31')
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        assert '0.00' in html or '₹0' in html
        assert '0' in html
        assert '—' in html or 'No expenses' in html


if __name__ == '__main__':
    pytest.main([__file__, '-v'])