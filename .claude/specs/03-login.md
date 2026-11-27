# Spec: Login

## Overview
Implement user login for Spendly so registered users can sign in with their email and password. This feature processes the login form submit, validates input, verifies credentials against the database using Werkzeug's password checking, logs the user in via Flask session, and redirects to the landing page with a confirmation flash message.

## Depends on
- Step 01: Database Setup (`database/db.py`, `users` table)
- Step 02: Registration (`/register` route, user creation with hashed passwords)

## Routes
- `GET /login` — Render the login form (`templates/login.html`) — Public
- `POST /login` — Process login form, validate credentials, log in, and redirect — Public

## Database changes
No database schema changes needed. Uses existing `users` table:
- `email` (TEXT, UNIQUE, NOT NULL)
- `password_hash` (TEXT, NOT NULL)

## Templates
- **Create:** None
- **Modify:**
  - `templates/login.html` — Ensure form method is `POST`, action is `/login`, fields have correct `name` attributes (`email`, `password`), display error messages if present, and retain entered email value on validation failure.
  - `templates/base.html` — Flash message banner already present (added in Step 02).

## Files to change
- `app.py` — Add `POST` handler for `/login`, input validation, database query, password verification, session management, and error/flash messaging.
- `templates/login.html` — Wire up form fields and error display.

## Files to create
- `test_login.py` — Unit tests for login functionality.

## New dependencies
No new pip packages needed. Uses standard Flask session, `database.db.get_db()`, and `werkzeug.security.check_password_hash`.

## Rules for implementation
- No SQLAlchemy or ORMs — use direct SQLite via `database.db.get_db()`
- Parameterised queries only — e.g. `cursor.execute("SELECT * FROM users WHERE email = ?", (email,))`
- Passwords verified with `werkzeug.security.check_password_hash`
- Set `session['user_id'] = user.id` and `session['user_name'] = user.name` upon successful login
- Form validation:
  - Trim whitespace from email
  - Reject empty fields with user-friendly error message
  - Case-insensitively look up user by email
  - Reject invalid credentials with generic error ("Invalid email or password")
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`

## Definition of done
- [ ] `GET /login` displays the login form correctly
- [ ] Submitting valid credentials finds the user in the database and verifies the password
- [ ] Invalid email or wrong password shows a generic error message without revealing which part failed
- [ ] Empty/missing form fields show appropriate error messages without crashing
- [ ] Successful login logs the user in by setting session variables (`user_id`, `user_name`)
- [ ] Successful login redirects to the home/landing page with a success flash message ("Welcome back, [Name]!")
- [ ] `pytest test_login.py` passes all tests