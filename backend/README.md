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

Apply the schema, including accounts, articles, categories, tags, media, comments, publications, search, and notifications:

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

## Publications

Verified users can open a publication with `POST /api/v1/publications`. The caller becomes the owner and keeps their existing platform role. Independent articles remain articles with no publication.

Membership roles are owner, editor, author, and contributor. Owners manage settings, members, invitations, and every article. Editors can update the description, website, contact email, and branding. They can invite authors and contributors when `editors_can_invite` is true, and they can review and publish articles. Authors write and submit their own articles. Contributors write and submit their own drafts. When `requires_review` is true, only an editor or the owner publishes. When it is false, an author may publish their own draft. Contributors never publish.

Article URLs stay `GET /api/v1/posts/{slug}`. Slugs remain unique for the whole site, including publication articles. Public publication pages are `GET /api/v1/publications/{slug}` and `GET /api/v1/publications/{slug}/posts`. Private or inactive publications, and their articles, are not in those public responses.

Editorial state is stored separately from draft, published, and archived. The values are `draft`, `submitted`, `in_review`, `changes_requested`, `approved`, and `published`. Submit, start review, request changes, and approve are `POST` routes under `/api/v1/posts/{post_id}/`. Publishing still uses the existing publish route and still records content revisions. Each editorial change is appended to `editorial_events`.

Invitations expire after `INVITATION_EXPIRE_HOURS` (72). Only the SHA-256 hash is stored. The message uses the same fragment link as other account email. Acceptance checks the hash, expiry, single use, verified email, and an exact email match. New invitations are limited to `INVITATION_RATE_LIMIT_PER_HOUR` (20) and acceptance attempts to `INVITATION_ACCEPT_RATE_LIMIT_PER_HOUR` (10) while `AUTH_RATE_LIMIT_ENABLED` is true. Without SMTP, the response says email delivery is not configured. In development the unsent copy is under `backend/var/mail/`.

Publication management changes are appended to `publication_audit_logs`. Owners and editors can read that log. The API has no route to edit or delete it. A platform administrator can suspend an active publication, or reinstate a suspended one, by sending `status` on `PATCH /api/v1/publications/{publication_id}`. Owners archive and restore with the archive and restore routes.

## Search and discovery

PostgreSQL full-text search is the production search path. `posts.search_document` is plain text maintained by the application when an article, author name, publication name, category name, or tag name changes. A `BEFORE INSERT OR UPDATE` trigger writes `posts.search_vector` with `to_tsvector('simple', search_document)`. Search uses `websearch_to_tsquery('simple', :q)` and `ts_rank_cd`, with GIN index `ix_posts_search_vector`. The `simple` configuration does not stem words, so it stays usable for more than one language.

`pg_trgm` adds GIN indexes on titles, usernames, full names, publication names, category names, and tag names. Article search matches the vector, a title substring, or a title `similarity` above 0.3. Name discovery and suggestions use that same similarity threshold. Body text matches query words and is not fuzzy-matched.

Public search is `GET /api/v1/search`. An empty `q` returns the latest public articles and empty author, publication, category, and tag sections. No search event is stored for that request. `type=all` returns a separate page for each section.

```text
GET /api/v1/search?q=digital+gardens
GET /api/v1/search?q=kelp&type=articles&category=oceans&tag=kelp&sort=most_commented
GET /api/v1/discovery/articles?feed=trending
GET /api/v1/discovery/authors?q=ada
GET /api/v1/discovery/publications?q=harbor
GET /api/v1/posts/{post_id}/related?limit=5
GET /api/v1/search/suggestions?q=dig
POST /api/v1/posts/{slug}/view
```

Trending score, over a 7-day window:

```text
(views + 3 × approved comments) / (1 + age_in_days / 7)
```

Popular uses all-time views. Discussed uses all-time approved comments. Featured uses `is_featured`. None of these feeds is a machine-learning ranking.

Views are rows in `article_views`: article id, time, optional source, and a SHA-256 visitor hash. The hash input is the server secret plus either `user:{account id}` or the `X-Visitor-Id` header. IP addresses are not stored. The same hash and article are ignored for `VIEW_DEDUP_HOURS` (default 6). Authors viewing their own article, missing visitor identity, `health-check` and `kube-probe` user agents, and unpublished articles are not counted.

Suggestions require two characters, return at most 8 rows, and follow `SUGGESTION_RATE_LIMIT_PER_HOUR` when rate limiting is enabled. Draft titles and private publication names are omitted.

`search_events` stores the query, type, result count, and time for a non-empty search. It has no account column. Recording a search deletes events older than 90 days. `GET /api/v1/search/admin/stats` returns 30-day aggregates for an administrator.

The pytest suite matches `search_document` on SQLite, including one-character typos for longer words. Production queries stay in SQL.

## Notifications

Notifications are written in the same transaction as the action that caused them. Email is queued in `notification_deliveries` and sent by a separate worker, using the existing SMTP settings and development mail folder. Start the API and the worker independently:

```powershell
uvicorn app.main:app --reload
.\.venv\Scripts\python.exe -m app.workers.notification_worker
```

`--once` processes a single batch and exits. The worker claims at most `NOTIFICATION_WORKER_BATCH_SIZE` rows (20), commits the claim, then sends mail. Temporary failures retry up to `NOTIFICATION_EMAIL_MAX_ATTEMPTS` (5) with backoff from 60 seconds, doubling each time and capped at 15 minutes. Recipient rejection is permanent. Unconfigured SMTP is stored as `not_configured`, and in development a copy is written under `var/mail/`. A `sending` row older than 10 minutes is claimed again after a restart.

In-app and email switches are separate for comments, publications, editorial updates, and account notices. Defaults are on. Users can read, mark, and delete only their own in-app notifications. Comment bodies and invitation tokens are not stored in notifications. The existing invitation email still carries the acceptance token and does not follow the publication email switch. Password and verification mail are unchanged.

`GET /api/v1/notifications/admin/delivery` is limited to administrators and omits addresses and message bodies. Notification writes are limited to `NOTIFICATION_RATE_LIMIT_PER_HOUR` (60) while rate limiting is enabled.

## Analytics

Reports aggregate `posts`, `article_views`, `comments`, `users`, `publications`, and `publication_memberships` in SQL. They do not read search events or notification deliveries, and they do not cache totals. Draft, archived, and deleted articles are excluded. Only approved comments that are still present are counted.

Dates are UTC. Weeks start on Monday and months on the first day. The default window is the last 30 days. A midnight `date_to` includes that UTC day. The maximum window is 366 days. `compare=true` starts one window-length before `date_from` and ends one microsecond before it. Empty days, weeks, and months are zero-filled.

`engagement_rate` is approved comments divided by views, multiplied by 100, or 0 when views are 0. Views are stored read events, not unique readers. The view endpoint already drops owner self-views, duplicates inside `VIEW_DEDUP_HOURS`, health-check clients, and articles that are not publicly listed.

Author routes require a verified account and always use the caller's articles. Publication owners and editors see the publication's published articles. Authors and contributors see only their own articles in that publication. Suspended and removed members are rejected. A platform administrator does not gain publication analytics by role. Admin routes require a platform administrator. An active user is an active account that signed in during the window.

CSV routes stream `text/csv`, prefix formula-like cells with a quote, and stop author or publication files at 5,000 rows. They do not include email addresses or visitor hashes.

Migration `a9d4c2e81b37` adds the reporting indexes on top of `f8b1d4c62a90`.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The test suite overrides configuration and does not need a running PostgreSQL server.
