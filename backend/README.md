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

Apply the schema, including accounts, articles, categories, tags, media, and comments:

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

## Media

Verified authors upload JPEG, PNG, and WebP files to `POST /api/v1/media/upload`. The default maximum size is 10 MB. Pillow checks the bytes, corrects EXIF orientation, drops EXIF metadata, and writes original, large, medium, and thumbnail renditions. Large, medium, and thumbnail files are WebP. Their pixel edges are maximums: 1600, 800, and 320. Proportions stay intact.

`STORAGE_PROVIDER=local` writes to `MEDIA_STORAGE_DIR`, which defaults to `backend/var/media`. `STORAGE_PROVIDER=s3` uses `S3_BUCKET`, `S3_REGION`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY`. `S3_ENDPOINT_URL` is optional for S3-compatible services. `MEDIA_DELIVERY=private` returns signed URLs. `MEDIA_DELIVERY=public` uses `S3_PUBLIC_BASE_URL` when it is set. Local development leaves the S3 variables empty.

Authors attach their own ready images with `featured_image_id`. The older `featured_image` URL field still works. Public article responses include `featured_image_media`. A published article's image can be read without a token at `GET /api/v1/media/{media_id}/files/{variant}`. Deleting media never deletes an article. Media that an article still references cannot be removed. A failed storage delete does not mark the file as removed.

Uploads are limited to 20 per account per hour when `AUTH_RATE_LIMIT_ENABLED` is true.

## Comments

Signed-in users can comment on a published article when comments are open. Verified accounts are approved immediately. Unverified accounts stay pending until the article author or an administrator approves them. Hidden and rejected comments stay in the database and are omitted from public threads.

Threads have two levels: a root comment and replies to that root. A reply cannot contain another reply. HTML is stripped before the body is stored. The default limit is 2,000 characters (`COMMENT_MAX_LENGTH`). Duplicate text from the same person on the same thread is rejected. Comment creation is limited to `COMMENT_RATE_LIMIT_PER_HOUR` (30) and reports to `REPORT_RATE_LIMIT_PER_HOUR` (10) while rate limiting is enabled.

Soft-deleting a comment hides its text. Public replies remain under the placeholder "This comment was removed." The article author can approve, hide, and restore comments on that article only. Administrators can also reject comments. Each decision is appended to `moderation_logs`. Reports do not delete comments, and a person can report a comment only once.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The test suite overrides configuration and does not need a running PostgreSQL server.
