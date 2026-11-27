import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.secret_key = "test-secret-key"
    with app.test_client() as client:
        with app.app_context():
            from database.db import init_db, seed_db

            init_db()
            seed_db()
        yield client


def test_login_page_loads(client):
    """GET /login should return the login form."""
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Welcome back" in response.data


def test_successful_login(client):
    """Valid login should set session and redirect with flash message."""
    response = client.post(
        "/login",
        data={
            "email": "demo@spendly.com",
            "password": "demo123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with client.session_transaction() as sess:
        assert sess["user_id"] is not None
        assert sess["user_name"] == "Demo User"


def test_login_missing_fields(client):
    """Missing required fields should return an error."""
    response = client.post(
        "/login",
        data={"email": "", "password": ""},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"All fields are required" in response.data


def test_login_invalid_credentials(client):
    """Invalid email or wrong password should return a generic error."""
    # Wrong password for existing user
    response = client.post(
        "/login",
        data={
            "email": "demo@spendly.com",
            "password": "wrongpassword",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data

    # Non-existent email
    response = client.post(
        "/login",
        data={
            "email": "nonexistent@example.com",
            "password": "password123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_login_retains_email(client):
    """On validation error, email field should retain submitted value."""
    response = client.post(
        "/login",
        data={"email": "test@example.com", "password": ""},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b'test@example.com' in response.data