# ANDIKA

ANDIKA is an international blog publishing platform. This repository currently contains the backend API: accounts, sessions, articles, categories, tags, and media.

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
- Role checks for readers, verified authors, and verified administrators

Comments, subscriptions, and the frontend are not part of this stage.

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

## Tests

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

The suite uses an isolated in-memory database and does not need a running PostgreSQL server. It does not read or modify the development database.
