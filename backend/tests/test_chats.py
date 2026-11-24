"""Direct messages between two accounts."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.session import get_session_factory
from app.models.user import User, UserRole

PASSWORD = "Sup3rSecret12"


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
    assert response.status_code == 201, response.text


def _promote(email: str) -> None:
    database = get_session_factory()()
    try:
        user = database.scalar(select(User).where(User.email == email))
        assert user is not None
        user.role = UserRole.READER
        user.is_verified = True
        database.commit()
    finally:
        database.close()


def _login(client: TestClient, email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_two_people_can_exchange_messages_and_others_cannot(client: TestClient) -> None:
    _register(client, "AdaChat", "ada.chat@example.com")
    _register(client, "BeaChat", "bea.chat@example.com")
    _register(client, "CidChat", "cid.chat@example.com")
    _promote("ada.chat@example.com")
    _promote("bea.chat@example.com")
    _promote("cid.chat@example.com")
    ada = _login(client, "ada.chat@example.com")
    bea = _login(client, "bea.chat@example.com")
    cid = _login(client, "cid.chat@example.com")

    assert client.get("/api/v1/chats").status_code == 401
    self_chat = client.post("/api/v1/chats", headers=_auth(ada), json={"username": "AdaChat"})
    assert self_chat.status_code == 422
    missing = client.post("/api/v1/chats", headers=_auth(ada), json={"username": "Nobody"})
    assert missing.status_code == 404

    opened = client.post("/api/v1/chats", headers=_auth(ada), json={"username": "BeaChat"})
    assert opened.status_code == 200, opened.text
    conversation_id = opened.json()["id"]
    assert opened.json()["other"]["username"] == "BeaChat"
    assert "example.com" not in opened.text

    again = client.post("/api/v1/chats", headers=_auth(bea), json={"username": "AdaChat"})
    assert again.json()["id"] == conversation_id

    sent = client.post(
        f"/api/v1/chats/{conversation_id}/messages",
        headers=_auth(ada),
        json={"body": "  Hello from the desk.  "},
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["body"] == "Hello from the desk."
    assert sent.json()["mine"] is True

    reply = client.post(
        f"/api/v1/chats/{conversation_id}/messages",
        headers=_auth(bea),
        json={"body": "Received."},
    )
    assert reply.status_code == 200

    ada_messages = client.get(
        f"/api/v1/chats/{conversation_id}/messages",
        headers=_auth(ada),
    )
    assert [item["body"] for item in ada_messages.json()["items"]] == [
        "Hello from the desk.",
        "Received.",
    ]
    assert ada_messages.json()["items"][1]["mine"] is False

    listing = client.get("/api/v1/chats", headers=_auth(bea))
    assert listing.status_code == 200
    assert listing.json()[0]["last_message"] == "Received."
    assert "example.com" not in listing.text

    hidden = client.get(f"/api/v1/chats/{conversation_id}/messages", headers=_auth(cid))
    assert hidden.status_code == 404
    blocked = client.post(
        f"/api/v1/chats/{conversation_id}/messages",
        headers=_auth(cid),
        json={"body": "I should not be here."},
    )
    assert blocked.status_code == 404
