import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.secret_key = "test-secret-key"
    import os
    if os.path.exists("spendly.db"):
        os.remove("spendly.db")
    with app.test_client() as client:
        with app.app_context():
            from database.db import init_db, seed_db

            init_db()
            seed_db()
        yield client


def test_register_page_loads(client):
    """GET /register should return the registration form."""
    response = client.get("/register")
    assert response.status_code == 200
    assert b"Create your account" in response.data


def test_successful_registration(client):
    """Valid registration should create user, set session, and redirect."""
    response = client.post(
        "/register",
        data={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "password123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with client.session_transaction() as sess:
        assert sess["user_id"] is not None
        assert sess["user_name"] == "Alice"


def test_registration_missing_fields(client):
    """Missing required fields should return an error."""
    response = client.post(
        "/register",
        data={"name": "", "email": "", "password": ""},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"All fields are required" in response.data


def test_registration_short_password(client):
    """Password shorter than 8 chars should return an error."""
    response = client.post(
        "/register",
        data={
            "name": "Bob",
            "email": "bob@example.com",
            "password": "short",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"at least 8 characters" in response.data


def test_registration_duplicate_email(client):
    """Existing email should return an error."""
    client.post(
        "/register",
        data={
            "name": "Carol",
            "email": "carol@example.com",
            "password": "password123",
        },
    )
    response = client.post(
        "/register",
        data={
            "name": "Carol2",
            "email": "carol@example.com",
            "password": "password123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert b"already registered" in response.data