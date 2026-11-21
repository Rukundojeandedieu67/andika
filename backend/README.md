# ANDIKA backend

FastAPI backend for the ANDIKA publishing platform. It provides configuration, PostgreSQL connectivity, migrations, health checks, and authentication with user management.

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ (PostgreSQL 17 is installed on the current development machine)
- The virtual environment at `backend/.venv`

## Configure

From `backend`:

```powershell
copy .env.example .env
```

Edit `.env` if the database user, password, or host differ. Production must set a unique `JWT_SECRET_KEY` of at least 32 characters and a non-default `DATABASE_URL`. The application refuses to start in production when those values are placeholders.

Create the local database:

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -c "CREATE USER andika WITH PASSWORD 'andika';"
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -c "CREATE DATABASE andika OWNER andika;"
```

A Supabase PostgreSQL URL can be used instead. Keep the `postgresql+psycopg://` driver prefix, or use `postgresql://` and the application will normalize it.

## Migrate

Apply the schema, including accounts, articles, categories, and tags:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe history
```

`upgrade head` needs a reachable database. `alembic upgrade head --sql` renders the SQL without connecting. Application startup does not create tables.

## Run

From `backend`, with `.venv` active:

```powershell
uvicorn app.main:app --reload
```

Or without activating the environment:

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

- API root: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/api/v1/health`
- Database health: `http://127.0.0.1:8000/api/v1/health/database`
- Interactive docs: `http://127.0.0.1:8000/docs`

The process health check does not require PostgreSQL. The database health check runs `SELECT 1` and returns HTTP 503 when the database cannot be reached. Responses do not include credentials or SQL errors.

## Authentication

Interactive docs list the routes under the `auth` and `users` tags. The implemented routes are:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/reset-password`
- `POST /api/v1/auth/verify-email`
- `POST /api/v1/auth/resend-verification`
- `GET /api/v1/users/me`
- `PATCH /api/v1/users/me`

Registration always creates a reader. Login accepts email and password and returns a short-lived JWT plus an opaque refresh token. Refresh tokens are stored only as SHA-256 hashes, rotated on use, and the whole session family is revoked if a used token is presented again. Logout revokes that family, so the access token stops working immediately.

Browser clients should keep the access token in memory. Login and refresh also set an `andika_refresh_token` cookie: HttpOnly, SameSite=Strict, path `/api/v1/auth`, and Secure in production. Logout clears that cookie. Do not put refresh tokens in `localStorage` or in query strings. Email links carry reset and verification tokens in the URL fragment (`#token=`).

Password recovery and verification return the same message whether or not the address exists. If `SMTP_HOST` and `SMTP_FROM_EMAIL` are empty, that message says email delivery is not configured. In development, the unsent message is also written under `backend/var/mail/` so the verification or reset link can be used locally. That file is not a sent email. When SMTP is configured, the message says a message has been sent. Failures are logged by template name and exception type only.

## Articles

Article routes are under the `posts` tag. Readers can list and open published articles. Verified authors manage their own drafts, including publish, unpublish, archive, and soft delete. Verified administrators can manage every article. Drafts, archived articles, and deleted articles are excluded from public results. Changing the slug of a published article keeps the previous slug as a permanent redirect. Content edits are stored as numbered revisions for the owner and administrators. Changing only the category or tags does not create a revision.

Public article lists accept `category` and `tag` slug filters. A category filter includes that category and its visible descendants. The two filters can be combined with the existing search and pagination parameters.

## Categories and tags

Categories are global platform records managed by verified administrators. Authors select a category when creating or editing an article. They cannot create, rename, activate, or delete categories.

Names are unique after collapsing whitespace and ignoring case. The stored name keeps the first saved capitalization. Slugs are unique. Nesting stops at three levels: a category cannot be its own parent, and it cannot be moved under one of its own children. Public responses omit an inactive category and any category whose parent is inactive.

Deleting a category with children is rejected. Deleting a category with no children sets `category_id` to null on its articles. The articles are not deleted.

Verified authors create reusable tags. Public tag routes return only tags attached to a published article. Administrators can list, rename, and delete every tag. Deleting a tag removes the article associations and leaves the articles in place.

Apply the taxonomy migration with the same Alembic command used for the rest of the schema:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The test suite overrides configuration and does not need a running PostgreSQL server.
