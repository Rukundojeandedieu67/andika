"""Media upload, processing, ownership, and article integration tests."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.core.config import get_settings
from app.core.storage_config import get_storage, set_storage_override
from app.database.session import get_session_factory
from app.infrastructure.storage.base import Storage, StorageError
from app.infrastructure.storage.local import LocalStorage
from app.models.media import Media, MediaStatus, StorageProvider
from app.models.user import User, UserRole

PASSWORD = "Sup3rSecret12"


class _DeleteFails(Storage):
    def __init__(self, inner: Storage) -> None:
        self.inner = inner

    def save(self, key: str, data: bytes, content_type: str) -> None:
        self.inner.save(key, data, content_type)

    def delete(self, key: str) -> None:
        raise StorageError("The stored file could not be removed.")

    def exists(self, key: str) -> bool:
        return self.inner.exists(key)

    def read(self, key: str) -> bytes:
        return self.inner.read(key)

    def get_url(self, key: str) -> str:
        return self.inner.get_url(key)


class _FailSecondSave(Storage):
    def __init__(self, inner: Storage) -> None:
        self.inner = inner
        self.saves = 0

    def save(self, key: str, data: bytes, content_type: str) -> None:
        self.saves += 1
        if self.saves == 2:
            raise StorageError("The file could not be stored.")
        self.inner.save(key, data, content_type)

    def delete(self, key: str) -> None:
        self.inner.delete(key)

    def exists(self, key: str) -> bool:
        return self.inner.exists(key)

    def read(self, key: str) -> bytes:
        return self.inner.read(key)

    def get_url(self, key: str) -> str:
        return self.inner.get_url(key)


def _image(
    image_format: str,
    size: tuple[int, int] = (40, 20),
    *,
    orientation: int | None = None,
) -> bytes:
    image = Image.new("RGB", size, (20, 40, 60))
    buffer = BytesIO()
    if orientation is None:
        image.save(buffer, format=image_format)
    else:
        exif = Image.Exif()
        exif[274] = orientation
        image.save(buffer, format=image_format, exif=exif.tobytes())
    return buffer.getvalue()


def _register(client: TestClient, username: str, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "full_name": username,
        },
    )
    assert response.status_code == 201


def _promote(email: str, role: UserRole) -> None:
    database = get_session_factory()()
    try:
        user = database.scalar(select(User).where(User.email == email))
        assert user is not None
        user.role = role
        user.is_verified = True
        database.commit()
    finally:
        database.close()


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _author(client: TestClient, username: str, email: str) -> str:
    _register(client, username, email)
    _promote(email, UserRole.AUTHOR)
    return _login(client, email)


def _upload(
    client: TestClient,
    token: str,
    data: bytes,
    *,
    filename: str = "photo.jpg",
    content_type: str = "image/jpeg",
    **fields: str,
) -> object:
    return client.post(
        "/api/v1/media/upload",
        headers=_auth(token),
        files={"file": (filename, data, content_type)},
        data=fields,
    )


def _variant(body: dict[str, object], kind: str) -> dict[str, object]:
    variants = body["variants"]
    assert isinstance(variants, list)
    found = next(item for item in variants if item["kind"] == kind)
    assert isinstance(found, dict)
    return found


def test_author_uploads_supported_images_and_reader_cannot(client: TestClient) -> None:
    author = _author(client, "Ada", "ada.media@example.com")
    _register(client, "Reader", "reader.media@example.com")
    _promote("reader.media@example.com", UserRole.READER)
    reader = _login(client, "reader.media@example.com")

    jpeg = _upload(client, author, _image("JPEG"), alt_text="A hillside")
    assert jpeg.status_code == 201, jpeg.text
    body = jpeg.json()
    assert body["mime_type"] == "image/jpeg"
    assert body["width"] == 40
    assert body["height"] == 20
    assert body["alt_text"] == "A hillside"
    assert body["status"] == "ready"
    assert {item["kind"] for item in body["variants"]} == {
        "original",
        "large",
        "medium",
        "thumbnail",
    }
    assert "storage_key" not in body
    assert _variant(body, "large")["width"] == 40
    assert _variant(body, "large")["height"] == 20

    png = _upload(
        client,
        author,
        _image("PNG", (400, 200)),
        filename="wide.png",
        content_type="image/png",
    )
    assert png.status_code == 201, png.text
    thumb = _variant(png.json(), "thumbnail")
    assert thumb["width"] == 320
    assert thumb["height"] == 160
    assert thumb["mime_type"] == "image/webp"

    webp = _upload(
        client,
        author,
        _image("WEBP"),
        filename="still.webp",
        content_type="image/webp",
    )
    assert webp.status_code == 201, webp.text

    blocked = _upload(client, reader, _image("JPEG"))
    assert blocked.status_code == 403


def test_upload_rejects_invalid_spoofed_and_oversized_files(client: TestClient) -> None:
    author = _author(client, "Ada", "ada.invalid@example.com")
    corrupt = _upload(client, author, b"not-an-image", filename="note.jpg")
    assert corrupt.status_code == 422

    png_as_jpeg = _upload(
        client,
        author,
        _image("PNG"),
        filename="spoof.jpg",
        content_type="image/jpeg",
    )
    assert png_as_jpeg.status_code == 422
    assert "declared type" in png_as_jpeg.json()["error"]["message"]

    script = _upload(
        client,
        author,
        _image("JPEG"),
        filename="page.html",
        content_type="image/jpeg",
    )
    assert script.status_code == 422

    current = get_settings()
    client.app.dependency_overrides[get_settings] = lambda: current.model_copy(
        update={"media_max_upload_bytes": 80}
    )
    oversized = _upload(client, author, _image("JPEG"))
    client.app.dependency_overrides.pop(get_settings, None)
    assert oversized.status_code == 413

    library = client.get("/api/v1/media/mine", headers=_auth(author))
    assert library.json()["total"] == 0


def test_exif_orientation_and_duplicate_content(client: TestClient) -> None:
    author = _author(client, "Ada", "ada.exif@example.com")
    payload = _image("JPEG", (30, 10), orientation=6)
    uploaded = _upload(client, author, payload, filename="turned.jpg")
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["width"] == 10
    assert uploaded.json()["height"] == 30

    again = _upload(client, author, payload, filename="turned-again.jpg")
    assert again.status_code == 200
    assert again.json()["id"] == uploaded.json()["id"]
    library = client.get("/api/v1/media/mine", headers=_auth(author))
    assert library.json()["total"] == 1


def test_library_privacy_pagination_and_metadata(client: TestClient) -> None:
    author = _author(client, "Ada", "ada.library@example.com")
    other = _author(client, "Bea", "bea.library@example.com")
    first = _upload(client, author, _image("JPEG"), title="Hillside morning")
    _upload(
        client,
        author,
        _image("PNG", (32, 32)),
        filename="b.png",
        content_type="image/png",
    )
    _upload(client, author, _image("JPEG", (24, 24)), filename="c.jpg")
    page = client.get("/api/v1/media/mine?page_size=2", headers=_auth(author))
    assert page.status_code == 200
    assert page.json()["total"] == 3
    assert len(page.json()["items"]) == 2

    found = client.get("/api/v1/media/mine?search=Hillside", headers=_auth(author))
    assert found.json()["total"] == 1
    typed = client.get("/api/v1/media/mine?mime_type=image/png", headers=_auth(author))
    assert typed.json()["total"] == 1

    media_id = first.json()["id"]
    updated = client.patch(
        f"/api/v1/media/{media_id}",
        headers=_auth(author),
        json={"alt_text": "Morning hill", "caption": "North slope"},
    )
    assert updated.status_code == 200
    assert updated.json()["alt_text"] == "Morning hill"

    hidden = client.get(f"/api/v1/media/{media_id}", headers=_auth(other))
    assert hidden.status_code == 404
    other_library = client.get("/api/v1/media/mine", headers=_auth(other))
    assert other_library.json()["total"] == 0


def test_article_uses_owned_ready_media_only(client: TestClient) -> None:
    author = _author(client, "Ada", "ada.feature@example.com")
    other = _author(client, "Bea", "bea.feature@example.com")
    _register(client, "Reader", "reader.feature@example.com")
    _promote("reader.feature@example.com", UserRole.READER)
    reader = _login(client, "reader.feature@example.com")
    uploaded = _upload(client, author, _image("JPEG"), alt_text="Cover")
    media_id = uploaded.json()["id"]
    file_url = str(_variant(uploaded.json(), "large")["url"])

    private = client.get(file_url)
    assert private.status_code == 404
    owned = client.get(file_url, headers=_auth(author))
    assert owned.status_code == 200
    assert owned.headers["content-type"].startswith("image/webp")

    created = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={
            "title": "Article With a Featured Image",
            "content": "Published body for the image.",
            "featured_image_id": media_id,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["featured_image_media"]["id"] == media_id
    assert created.json()["featured_image_media"]["alt_text"] == "Cover"
    assert created.json()["featured_image"].endswith("/files/large")

    foreign = client.post(
        "/api/v1/posts",
        headers=_auth(other),
        json={"title": "Not My Image Article", "featured_image_id": media_id},
    )
    assert foreign.status_code == 404

    reader_upload = _upload(client, reader, _image("JPEG"))
    assert reader_upload.status_code == 403
    reader_post = client.post(
        "/api/v1/posts",
        headers=_auth(reader),
        json={"title": "Reader Article", "featured_image_id": media_id},
    )
    assert reader_post.status_code == 403

    missing = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={
            "title": "Missing Image Article",
            "featured_image_id": "11111111-1111-1111-1111-111111111111",
        },
    )
    assert missing.status_code == 404

    legacy = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={
            "title": "Legacy Image URL Article",
            "featured_image": "https://cdn.example/cover.jpg",
        },
    )
    assert legacy.status_code == 201
    assert legacy.json()["featured_image"] == "https://cdn.example/cover.jpg"
    assert legacy.json()["featured_image_media"] is None

    client.post(f"/api/v1/posts/{created.json()['id']}/publish", headers=_auth(author))
    public = client.get(file_url)
    assert public.status_code == 200
    assert "public" in public.headers["cache-control"]
    article = client.get(f"/api/v1/posts/{created.json()['slug']}")
    assert article.json()["featured_image_media"]["id"] == media_id


def test_failed_and_deleted_media_cannot_be_attached(client: TestClient) -> None:
    author = _author(client, "Ada", "ada.failed@example.com")
    profile = client.get("/api/v1/users/me", headers=_auth(author))
    owner_id = UUID(str(profile.json()["id"]))
    failed_id = uuid4()
    database = get_session_factory()()
    try:
        database.add(
            Media(
                id=failed_id,
                owner_id=owner_id,
                original_filename="failed.jpg",
                storage_key=f"media/{owner_id}/{failed_id}/original.jpg",
                storage_provider=StorageProvider.LOCAL,
                mime_type="image/jpeg",
                file_extension=".jpg",
                file_size=12,
                checksum="b" * 64,
                status=MediaStatus.FAILED,
            )
        )
        database.commit()
    finally:
        database.close()

    failed = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={"title": "Failed Image Article", "featured_image_id": str(failed_id)},
    )
    assert failed.status_code == 422

    uploaded = _upload(client, author, _image("JPEG"))
    removed = client.delete(
        f"/api/v1/media/{uploaded.json()['id']}", headers=_auth(author)
    )
    assert removed.status_code == 204
    attached = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={
            "title": "Deleted Image Article",
            "featured_image_id": uploaded.json()["id"],
        },
    )
    assert attached.status_code == 404
    library = client.get("/api/v1/media/mine", headers=_auth(author))
    assert uploaded.json()["id"] not in [item["id"] for item in library.json()["items"]]
    assert library.json()["total"] == 1


def test_referenced_media_and_storage_failures(client: TestClient) -> None:
    _register(client, "Admin", "admin.media@example.com")
    _promote("admin.media@example.com", UserRole.ADMIN)
    admin = _login(client, "admin.media@example.com")
    author = _author(client, "Ada", "ada.delete@example.com")
    uploaded = _upload(client, author, _image("JPEG"))
    media_id = uploaded.json()["id"]
    created = client.post(
        "/api/v1/posts",
        headers=_auth(author),
        json={
            "title": "Article Holding an Image",
            "content": "Body stays after image rules run.",
            "featured_image_id": media_id,
        },
    )
    assert created.status_code == 201
    blocked = client.delete(f"/api/v1/media/{media_id}", headers=_auth(author))
    assert blocked.status_code == 409
    article = client.get(
        f"/api/v1/posts/mine/{created.json()['id']}", headers=_auth(author)
    )
    assert article.status_code == 200
    assert article.json()["featured_image_media"]["id"] == media_id

    client.patch(
        f"/api/v1/posts/{created.json()['id']}",
        headers=_auth(author),
        json={"featured_image_id": None},
    )
    set_storage_override(_DeleteFails(get_storage()))
    storage_error = client.delete(f"/api/v1/media/{media_id}", headers=_auth(author))
    set_storage_override(None)
    assert storage_error.status_code == 503
    still_there = client.get(f"/api/v1/media/{media_id}", headers=_auth(author))
    assert still_there.status_code == 200

    removed = client.delete(f"/api/v1/media/admin/{media_id}", headers=_auth(admin))
    assert removed.status_code == 204
    assert client.get(f"/api/v1/media/{media_id}", headers=_auth(author)).status_code == 404
    assert (
        client.get(
            f"/api/v1/posts/mine/{created.json()['id']}", headers=_auth(author)
        ).status_code
        == 200
    )

    before = {
        path
        for path in Path(get_settings().media_storage_dir).rglob("*")
        if path.is_file()
    }
    set_storage_override(_FailSecondSave(get_storage()))
    partial = _upload(
        client,
        author,
        _image("PNG"),
        filename="partial.png",
        content_type="image/png",
    )
    set_storage_override(None)
    assert partial.status_code == 503
    assert client.get("/api/v1/media/mine", headers=_auth(author)).json()["total"] == 0
    after = {
        path
        for path in Path(get_settings().media_storage_dir).rglob("*")
        if path.is_file()
    }
    assert after == before


def test_local_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path / "media")
    try:
        storage.save("../secret.txt", b"nope", "text/plain")
    except StorageError:
        pass
    else:
        raise AssertionError("Path traversal was stored.")
    assert not (tmp_path / "secret.txt").exists()
    storage.save("media/ab/file.webp", b"webp", "image/webp")
    assert storage.exists("media/ab/file.webp")
    assert storage.read("media/ab/file.webp") == b"webp"
