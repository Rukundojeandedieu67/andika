# ANDIKA

ANDIKA is an international blog publishing platform. This repository contains the FastAPI backend and the React frontend for accounts, articles, categories, tags, media, comments, publications, search, notifications, analytics, and administration.

The API is a FastAPI application backed by PostgreSQL. Interactive documentation is served at `/docs` once the server is running.

## What works now

- Account registration, login, logout, and profile updates
- Short-lived JWT access tokens and rotating refresh tokens
- Password reset and email verification
- Draft, publish, unpublish, archive, and soft-delete for articles
- Public article listing and slug lookup, with redirects when a published slug changes
- Revision history for article content
- Global categories, reusable tags, and article discovery by category or tag
- Image uploads, WebP variants, and featured images on articles
- Threaded comments, reports, and moderation
- Publications with membership roles, invitations, and editorial review
- Public search, discovery feeds, related articles, suggestions, and view counts
- Private in-app notifications and preference-controlled email delivery
- Analytics for authors, publications, and administrators, including CSV export
- Role checks for readers, verified authors, and verified administrators

There is no subscription product. The frontend is the React application in `frontend/`.

## Stack

- Python 3.11
- FastAPI and Pydantic v2
- PostgreSQL with SQLAlchemy 2.x and Alembic
- Argon2id password hashing
- Pytest

## Layout

```text
andika/
├── README.md
├── frontend/       React application
└── backend/
    ├── app/            API, models, and services
    ├── alembic/        Database migrations
    ├── tests/          Automated tests
    ├── requirements.txt
    └── .env.example
```

Operational detail for the API lives in [backend/README.md](backend/README.md).

## Run the API

From `backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with the local database URL and a development JWT secret. Production rejects placeholder secrets and the default database URL.

Create the database, apply migrations, and start the server:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

| URL | Purpose |
|---|---|
| http://127.0.0.1:8000/ | API identity |
| http://127.0.0.1:8000/docs | Interactive docs |
| http://127.0.0.1:8000/api/v1/health | Process health |
| http://127.0.0.1:8000/api/v1/health/database | Database connectivity |

The process health check does not need PostgreSQL. The database check returns HTTP 503 when the database cannot be reached, without exposing credentials or SQL errors.

## Run the frontend

From `frontend`, with the API already running on `127.0.0.1:8000`:

```powershell
npm install
copy .env.example .env
npm run dev
```

Open http://localhost:5173. `VITE_API_BASE_URL` stays `/api/v1`. Vite proxies `/api` to the local API so the refresh cookie can stay SameSite=Strict. Do not point the browser at `127.0.0.1:5173` and the API base at `localhost`, or the other way around.

`npm run build` writes `frontend/dist`. Serve that directory on the same origin as `/api`, or put a reverse proxy in front of both. The access token stays in memory. The refresh token is the HttpOnly cookie and must not be stored in localStorage or sessionStorage.

There is no user-directory API. Administration covers platform analytics, articles, categories, tags, comments, reports, media, search totals, and email delivery counts.

Startup does not create tables. Schema changes go through Alembic.

## Accounts

Registration creates a reader. An author or administrator must be assigned outside public registration, and those roles require a verified email address before they can publish or administer articles.

Login returns a short-lived access token and an opaque refresh token. Refresh tokens are stored only as hashes, rotated on every use, and the whole session family is revoked if a used token is presented again. Logout revokes that family, so the access token stops working immediately.

Browser clients should keep the access token in memory. The refresh token is also set as the `andika_refresh_token` cookie: HttpOnly, SameSite=Strict, limited to `/api/v1/auth`, and Secure in production. Do not store it in `localStorage` or put it in a query string.

Password reset and verification links carry the token in the URL fragment (`#token=`). If SMTP is not configured, the API says delivery is not configured and, in development, writes the unsent message under `backend/var/mail/`.

A password must be 12 to 1024 characters, include a letter and a number, and must not contain the username or the email name.

## Articles

Public readers can list and open published articles. Drafts, archived articles, and deleted articles are excluded.

Verified authors create drafts and can publish, unpublish, archive, and soft-delete their own work. Verified administrators can do that for every article and can list drafts and archives. The author is taken from the access token, not from the request body.

Publishing requires article content and records `published_at`. Changing the slug of a published article keeps the old slug as a permanent redirect. Edits to the title, excerpt, or content are stored as numbered revisions visible to the owner and to administrators.

Main routes:

- `GET /api/v1/posts` and `GET /api/v1/posts/{slug}`
- `POST /api/v1/posts`
- `GET /api/v1/posts/mine` and `GET /api/v1/posts/mine/{post_id}`
- `PATCH /api/v1/posts/{post_id}`
- `POST /api/v1/posts/{post_id}/publish`
- `POST /api/v1/posts/{post_id}/unpublish`
- `POST /api/v1/posts/{post_id}/archive`
- `DELETE /api/v1/posts/{post_id}`
- `GET /api/v1/posts/{post_id}/revisions`
- `GET /api/v1/posts/admin/all`

Public listing also accepts `category` and `tag` slug filters, including both together:

```http
GET /api/v1/posts?category=technology&tag=python
```

A category filter includes that category and its visible child categories. Drafts, archived articles, and deleted articles stay out of public results.

## Categories and tags

Categories are global. A verified administrator creates, renames, nests, activates, deactivates, and deletes them. Authors choose an existing category for their own articles. Readers and authors cannot change the category catalog.

A category name is stored with its capitalization, and uniqueness uses the name with surrounding and repeated spaces collapsed and with case ignored. `Technology` and `TECHNOLOGY` are the same category. Slugs are unique. A category may have a parent, but it cannot be its own parent, cannot sit under one of its children, and cannot be nested more than three levels.

An inactive category, and every category under an inactive parent, is omitted from public category and article results. Assigning an inactive category to an article is rejected.

Deleting a category that still has children is rejected. Deleting a leaf category clears that category on existing articles and does not delete the articles.

Tags are reusable. A verified author can create one. The same name rules apply. Public tag lists and tag pages include only tags used by at least one published article. Administrators can list every tag, rename a tag, or delete it. Deleting a tag removes it from articles and leaves the articles in place.

```http
POST /api/v1/categories
{"name": "Technology", "description": "Platform and tools"}

POST /api/v1/tags
{"name": "Python"}

POST /api/v1/posts
{"title": "The Future of Artificial Intelligence", "content": "Article content...", "category_id": "<category uuid>", "tag_ids": ["<tag uuid>"]}
```

Category routes:

- `GET /api/v1/categories`
- `GET /api/v1/categories/{slug}`
- `GET /api/v1/categories/{slug}/posts`
- `POST /api/v1/categories`
- `PATCH /api/v1/categories/{category_id}`
- `GET /api/v1/categories/admin/all`
- `PATCH /api/v1/categories/admin/{category_id}/status`
- `DELETE /api/v1/categories/admin/{category_id}`

Tag routes:

- `GET /api/v1/tags`
- `GET /api/v1/tags/{slug}`
- `GET /api/v1/tags/{slug}/posts`
- `POST /api/v1/tags`
- `GET /api/v1/tags/admin/all`
- `PATCH /api/v1/tags/admin/{tag_id}`
- `DELETE /api/v1/tags/admin/{tag_id}`

## Media

Verified authors and administrators can upload JPEG, PNG, and WebP images. Readers cannot upload. The default limit is 10 MB (`MEDIA_MAX_UPLOAD_BYTES`). The file is decoded with Pillow, EXIF orientation is applied, and the stored image does not keep the original EXIF data. Each upload produces four renditions: original, large (1600px), medium (800px), and thumbnail (320px). Those sizes are maximum edges. Aspect ratio is preserved, and small images are not enlarged.

Uploads are stored under `backend/var/media` in development. The original filename is never used as a filesystem path. Set `STORAGE_PROVIDER=s3` to use an S3-compatible bucket. Credentials belong in the environment, not in source. Private delivery uses signed URLs. Public delivery uses `S3_PUBLIC_BASE_URL` or the bucket URL. Local development does not need S3 settings.

An author can set `featured_image_id` on an article they own, using their own ready image. Administrators can attach any ready image. A legacy `featured_image` URL is still accepted. Article responses include `featured_image_media` when a media record is attached, and `featured_image` remains a URL. Deleting an image does not delete the article. An image that is still attached to an article cannot be deleted until it is detached. If storage removal fails, the media record stays and the API returns an error.

The same image uploaded again by the same owner returns the existing record. Images on a published article can be fetched without authentication. Other images require the owner or an administrator.

```http
POST /api/v1/media/upload
Content-Type: multipart/form-data

file: photo.jpg
alt_text: Cover photograph

POST /api/v1/posts
{"title": "A field note", "content": "Article content...", "featured_image_id": "<media uuid>"}
```

Media routes:

- `POST /api/v1/media/upload`
- `GET /api/v1/media/mine`
- `GET /api/v1/media/{media_id}`
- `PATCH /api/v1/media/{media_id}`
- `DELETE /api/v1/media/{media_id}`
- `GET /api/v1/media/{media_id}/files/{variant}`
- `GET /api/v1/media/admin/all`
- `DELETE /api/v1/media/admin/{media_id}`

## Comments

Signed-in readers, authors, and administrators can comment on a published article when `allow_comments` is true. Drafts, archived articles, and deleted articles do not accept comments, and their discussions are not public.

A comment is either a root comment or a reply to a root comment. Replies cannot contain further replies, and a reply must belong to the same article as its parent. Only an approved comment can be replied to.

Verified accounts are approved immediately. Unverified accounts stay `pending` until the article's author or an administrator approves them. `hidden` and `rejected` comments are kept, but they are not public. A rejected comment is never published on its own.

Comment text is stored as plain text. HTML tags are removed, whitespace is collapsed, and an empty result is rejected. The default maximum length is 2,000 characters. New comments are limited to 30 per account per hour, and reports to 10 per hour, while `AUTH_RATE_LIMIT_ENABLED` is true. Posting the same body again on the same thread is rejected.

Deleting a comment hides its text and keeps the author. If that comment has public replies, the thread shows "This comment was removed." and the replies stay. The public list returns approved threads only and does not include moderation status.

The article's author can approve a pending comment, hide one, or restore a hidden one. An author cannot reject comments and cannot moderate another author's article. Administrators can approve, hide, reject, and restore comments across the platform. Every status change is written to an audit log that ordinary users cannot edit.

Anyone signed in can report an approved comment. Reasons are spam, harassment, hate speech, misinformation, inappropriate content, and other. The same person cannot report the same comment twice. A report does not delete the comment. Reporter email addresses are not returned.

```http
POST /api/v1/posts/<post uuid>/comments
{"body": "This is a clear and useful note."}

POST /api/v1/posts/<post uuid>/comments/<comment uuid>/replies
{"body": "I agree, with one addition."}

POST /api/v1/comments/<comment uuid>/report
{"reason": "spam", "description": "Repeated promotion"}
```

Comment routes:

- `GET /api/v1/posts/{post_id}/comments`
- `POST /api/v1/posts/{post_id}/comments`
- `POST /api/v1/posts/{post_id}/comments/{comment_id}/replies`
- `GET /api/v1/comments/mine`
- `PATCH /api/v1/comments/{comment_id}`
- `DELETE /api/v1/comments/{comment_id}`
- `POST /api/v1/comments/{comment_id}/report`
- `GET /api/v1/posts/{post_id}/moderation/comments`
- `PATCH /api/v1/posts/{post_id}/moderation/comments/{comment_id}/status`
- `GET /api/v1/posts/{post_id}/moderation/reports`
- `PATCH /api/v1/posts/{post_id}/moderation/reports/{report_id}`
- `GET /api/v1/moderation/comments`
- `PATCH /api/v1/moderation/comments/{comment_id}/status`
- `GET /api/v1/moderation/reports`
- `PATCH /api/v1/moderation/reports/{report_id}`
- `GET /api/v1/moderation/logs`

## Publications

An author can still publish an article on their own. A publication is a separate editorial space, such as a magazine or journal, with its own members. Joining a publication does not change the person's platform role, and the publication owner is not a platform administrator.

Publication roles are owner, editor, author, and contributor. They apply only inside that publication. A suspended or removed member loses access immediately. A person may belong to more than one publication. Each publication has one owner. Ownership moves with `POST /api/v1/publications/{publication_id}/transfer-ownership`, which also turns the previous owner into an editor. The owner cannot be removed or suspended until ownership moves.

Public visitors can list and open active public publications and their published articles. Private, suspended, archived, and deleted publications are omitted. Their articles stay out of the public article list, the public slug route, and public comments.

Article slugs stay unique across the whole platform. A publication article keeps the same public URL as an independent article: `GET /api/v1/posts/{slug}`. Publication slugs are a separate namespace under `/api/v1/publications/{slug}`. The reserved publication slug is `mine`.

Publication articles keep the existing draft, published, and archived states. Review uses a separate `editorial_status`: draft, submitted, in review, changes requested, approved, and published. By default a publication requires review. Contributors and authors submit their own drafts. Editors and the owner move a submission into review, request changes, or approve it. Only an editor or the owner can publish while review is required. If the owner turns review off, an author can publish their own draft directly. Contributors cannot publish. Every transition is stored in an editorial history that the API does not edit or delete.

Invitations are single-use, expire, and are stored only as SHA-256 hashes. The email link carries the token in the URL fragment (`#token=`). Accepting requires a verified account whose email matches the invitation. An invitation cannot grant ownership or a platform administrator role. Creating and accepting invitations is rate limited per account while `AUTH_RATE_LIMIT_ENABLED` is true. If SMTP is not configured, the API says delivery is not configured. In development the unsent message is written under `backend/var/mail/`.

```http
POST /api/v1/publications
{"name": "North Review", "visibility": "public"}

POST /api/v1/publications/<publication uuid>/invitations
{"email": "editor@example.com", "role": "editor"}

POST /api/v1/invitations/accept
{"token": "<token from the email fragment>"}

POST /api/v1/posts
{"title": "Dispatch From the Field", "content": "The first report.", "publication_id": "<publication uuid>"}

POST /api/v1/posts/<post uuid>/submit
POST /api/v1/posts/<post uuid>/approve
POST /api/v1/posts/<post uuid>/publish
```

Publication routes:

- `GET /api/v1/publications`
- `POST /api/v1/publications`
- `GET /api/v1/publications/mine`
- `GET /api/v1/publications/{slug}`
- `GET /api/v1/publications/{slug}/posts`
- `GET /api/v1/publications/{publication_id}/manage`
- `PATCH /api/v1/publications/{publication_id}`
- `POST /api/v1/publications/{publication_id}/archive`
- `POST /api/v1/publications/{publication_id}/restore`
- `GET /api/v1/publications/{publication_id}/members`
- `PATCH /api/v1/publications/{publication_id}/members/{member_id}`
- `POST /api/v1/publications/{publication_id}/members/{member_id}/suspend`
- `POST /api/v1/publications/{publication_id}/members/{member_id}/remove`
- `POST /api/v1/publications/{publication_id}/transfer-ownership`
- `POST /api/v1/publications/{publication_id}/invitations`
- `GET /api/v1/publications/{publication_id}/invitations`
- `POST /api/v1/publications/{publication_id}/invitations/{invitation_id}/revoke`
- `POST /api/v1/invitations/accept`
- `GET /api/v1/publications/{publication_id}/editorial/posts`
- `GET /api/v1/publications/{publication_id}/editorial/posts/{post_id}`
- `GET /api/v1/publications/{publication_id}/editorial/submissions`
- `POST /api/v1/posts/{post_id}/submit`
- `POST /api/v1/posts/{post_id}/start-review`
- `POST /api/v1/posts/{post_id}/request-changes`
- `POST /api/v1/posts/{post_id}/approve`
- `GET /api/v1/publications/{publication_id}/audit-logs`

## Search and discovery

Search uses PostgreSQL. The application stores a plain-text `posts.search_document` in the same transaction as the article change. A database trigger then fills `posts.search_vector` with `to_tsvector('simple', search_document)`. The `simple` dictionary keeps words from any language instead of applying English stemming. A GIN index, `ix_posts_search_vector`, serves `websearch_to_tsquery`. Article text is ranked with `ts_rank_cd`. The document includes the title, subtitle, excerpt, body text with tags removed, category name, tag names, author name and username, and publication name. It is capped at 20,000 characters.

The document is rebuilt when the article text, category, or tags change, and when an author, publication, category, or tag is renamed. Drafts stay in the document, but public queries only return published articles that are independent or belong to an active public publication. Archived, deleted, private, suspended, and archived-publication articles are excluded. Search cards do not include the article body or a ranking score.

`pg_trgm` is enabled for partial names and title typos. Trigram GIN indexes cover article titles, usernames, full names, publication names, category names, and tag names. An article matches when its vector matches the query, its title contains the query, or the title similarity is above 0.3. Author, publication, and title suggestions use the same similarity threshold. Body text matches query words and is not fuzzy-matched.

`GET /api/v1/search` accepts `q`, `type` (`all`, `articles`, `authors`, `publications`, `categories`, `tags`), `category`, `tag`, `author` (username), `publication` (slug), `date_from`, `date_to`, `sort` (`relevance`, `newest`, `oldest`, `most_viewed`, `most_commented`), `page`, and `page_size`. An empty `q` returns the latest public articles and leaves the other sections empty. Filters still apply to that article list, and no analytics row is stored. A query with no word characters returns empty sections. `type=all` pages each section separately with the same page size. `author` is a username. `date_from` later than `date_to` is rejected.

Examples:

```text
GET /api/v1/search?q=digital+gardens
GET /api/v1/search?q=kelp&type=articles&category=oceans&sort=newest
GET /api/v1/search?type=authors&q=ada
```

Discovery feeds are `GET /api/v1/discovery/articles?feed=latest|trending|popular|discussed|featured`. There is no follow or subscription feed. Author and publication directories are `GET /api/v1/discovery/authors` and `GET /api/v1/discovery/publications`. Related articles are `GET /api/v1/posts/{post_id}/related`.

Trending is not a recommendation model. For the last 7 days:

```text
score = (views + 3 × approved comments) / (1 + age_in_days / 7)
```

Ties break on newer `published_at`, then article id. The weights live in code. Popular is the all-time view count. Discussed is the all-time count of approved comments that were not deleted. Featured is `is_featured` articles, newest first.

A view is `POST /api/v1/posts/{slug}/view`. Send `X-Visitor-Id` (8 to 80 letters, numbers, underscores, or hyphens) or call it while signed in. The stored value is a SHA-256 hash of the server secret and that identity. Raw addresses and account ids are not stored. The same visitor and article count once per `VIEW_DEDUP_HOURS` (6). The article author, a missing identity, and user agents containing `health-check` or `kube-probe` are not counted. An unpublished or private article returns 404. Optional `source` is 1 to 40 characters from `a-z`, `0-9`, `_`, and `-`.

Related articles share a category (5 points), tag (2 points each), publication (2 points), author (1 point), or a title word of at least four characters (1 point). The current article is excluded. At most 100 candidates are loaded, then ordered by score, newer publication date, and id. `limit` defaults to 5 and cannot exceed 20.

`GET /api/v1/search/suggestions?q=` needs at least two characters and returns at most 8 public titles, author names, publication names, categories, and tags. It is limited to `SUGGESTION_RATE_LIMIT_PER_HOUR` (60) per client address while `AUTH_RATE_LIMIT_ENABLED` is true.

A non-empty search stores the query text, type, result count, and time in `search_events`. It does not store an account or address. Rows older than 90 days are deleted when a new search is recorded. Administrators can read 30-day totals at `GET /api/v1/search/admin/stats`. There is no route for one person's search history.

The automated tests use SQLite, which has no `tsvector`. Those tests match the stored document in process, including a one-character typo on words of five characters or more. That fallback is not the production query.

## Notifications

A business action writes its in-app notification in the same database transaction. If that action rolls back, the notification rolls back with it. Email is a separate outbox row, `notification_deliveries`. The API process does not wait for SMTP. A failed email leaves the in-app notification in place.

The worker is a separate process:

```powershell
.\.venv\Scripts\python.exe -m app.workers.notification_worker
.\.venv\Scripts\python.exe -m app.workers.notification_worker --once
```

It polls every `NOTIFICATION_WORKER_POLL_SECONDS` (5), claims up to `NOTIFICATION_WORKER_BATCH_SIZE` (20) pending jobs, and commits that claim before opening SMTP. Temporary failures return to the queue with a backoff of 60 seconds, doubling each attempt, capped at 15 minutes. A job stops after `NOTIFICATION_EMAIL_MAX_ATTEMPTS` (5). A rejected recipient is not retried. When SMTP is not configured, the job is marked `not_configured` and is not described as sent. In development, that same attempt writes a copy under `backend/var/mail/`. A claim left in `sending` for 10 minutes is returned to the queue so a restarted worker can finish it.

Each event has one idempotency key, so a repeated call does not create a second notification. People are not notified about their own actions. Comment text is not copied into the notification. Invitation tokens stay in the existing invitation email and are not stored in the notification or the outbox. That invitation email is still sent even when publication email is disabled, because it is the acceptance credential. Verification and password messages are unchanged.

Preferences are independent for in-app and email, across comments, publications, editorial decisions, and account notices. Defaults are enabled. `GET` and `PATCH /api/v1/notifications/preferences` apply only to the signed-in user. Account notices are reserved; the current events are comments, publications, and editorial decisions.

```text
GET /api/v1/notifications?unread_only=true
GET /api/v1/notifications/unread-count
PATCH /api/v1/notifications/{notification_id}/read
POST /api/v1/notifications/read-all
DELETE /api/v1/notifications/{notification_id}
GET /api/v1/notifications/admin/delivery
```

The admin route returns delivery counts and failed job ids. It does not return addresses or message bodies.

## Analytics

Analytics read the records ANDIKA already stores. Article views come from `article_views`. Comments come from approved, non-deleted comments. Published articles are posts with status `published`, a publication time, and no deletion time. Search rows and notifications are not views. There is no second view counter and no cached summary table. A response describes the database at the time of the request.

Every timestamp is stored in UTC, and every day, week, and month is grouped in UTC. A week starts on Monday. A month starts on the first day. If a window begins on a Wednesday, the week bucket is still labeled with that Monday, but it counts only events inside the window. Missing buckets are returned as zeros.

`date_from` and `date_to` are inclusive. A `date_to` at UTC midnight includes that whole calendar day. Any other `date_to` is the exact instant. A missing offset is read as UTC. When both dates are omitted, the window is the 30 days ending now. When only one is sent, the other end is now or 30 days before `date_to`. A window longer than 366 days is rejected. `date_from` after `date_to` is rejected. `period` accepts `day`, `week`, or `month`. `compare=true` adds the preceding window. It starts one window-length before `date_from` and ends one microsecond before `date_from`, so the shared boundary is counted only in the current window.

```text
GET /api/v1/analytics/author/overview
GET /api/v1/analytics/author/articles?sort=views&page=1
GET /api/v1/analytics/author/timeseries?period=week
GET /api/v1/analytics/author/export
GET /api/v1/analytics/publications/{publication_id}/overview
GET /api/v1/analytics/publications/{publication_id}/articles
GET /api/v1/analytics/publications/{publication_id}/authors
GET /api/v1/analytics/publications/{publication_id}/export
GET /api/v1/analytics/admin/overview
GET /api/v1/analytics/admin/timeseries?period=month
GET /api/v1/analytics/admin/content
GET /api/v1/analytics/admin/export
```

An author report includes independent articles and publication articles that the signed-in user wrote. It does not accept another author's id. A verified publication writer can use it without a platform author role. Unverified accounts cannot.

Publication owners and editors see that publication's published articles, not the members' independent articles. Authors and contributors see only the articles they wrote there. Publications do not have a separate analytics permission, so contributors are not given the full report. Suspended and removed members are denied. Non-members, including a platform administrator who is not a member, receive the same not-found response as for a missing publication. A private publication stays available to its owner and editors and is hidden from everyone else.

The administrator report counts registered users, publications, published articles, views, and approved comments. An active user is an active account whose last sign-in falls in the selected window. That is not a reader count. Content is split into independent articles, articles in active public publications, and a count for everything else. The ranked list contains at most 10 publicly listed articles that were viewed in the window. Private titles are not included.

`engagement_rate = (approved_comments / views) * 100`. Zero views produce `0`, not an error. `average_views_per_article` divides all-time views by the number of currently published articles, and is `0` when that number is `0`. Article lists and exports count views and comments inside the selected window. Overview totals are all-time. Views are events. They are not unique readers. Owner self-views, repeats inside the deduplication window, health-check clients, and articles that are not publicly listed are never stored, so those reads stay at zero. Returning readership is omitted because the visitor hash must not be exposed and bot filtering is incomplete. Unpublishing an article removes it from later reports.

CSV exports use the same permission rules. The file is `text/csv` with `Content-Disposition` and `Cache-Control: no-store`. Author and publication exports contain at most 5,000 articles; `X-Andika-Export-Truncated` says whether the file stopped early. Cells that start with `=`, `+`, `-`, `@`, a tab, or a carriage return are prefixed with a quote. Exports omit email addresses, visitor hashes, invitation tokens, and notification bodies. The admin file is the content summary plus the public ranking, not a user directory.

The migration `a9d4c2e81b37` adds indexes for these filters. It does not copy or rewrite existing rows.

## Tests

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The suite uses an isolated in-memory database and does not need a running PostgreSQL server. It does not read or modify the development database.
