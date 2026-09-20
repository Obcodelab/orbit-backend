from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from modules.auth.services import google_oauth


async def test_google_login_redirects_to_google_with_signed_state(
    client: AsyncClient,
):
    response = await client.get("/api/v1/auth/google/login", follow_redirects=False)

    assert response.status_code == 307
    location = response.headers["location"]
    assert "accounts.google.com" in location
    assert "state=" in location


async def test_google_callback_creates_new_user(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    state = google_oauth.create_state("test-code-verifier")
    fake_id_info = {
        "email": "googleuser@example.com",
        "given_name": "Google",
        "family_name": "User",
        "picture": "https://example.com/pic.jpg",
    }
    monkeypatch.setattr(
        google_oauth, "exchange_code", AsyncMock(return_value=fake_id_info)
    )

    response = await client.get(
        "/api/v1/auth/google/callback",
        params={"code": "fake-code", "state": state},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == fake_id_info["email"]
    assert body["user"]["login_method"] == "google"
    assert body["user"]["email_verified"] is True
    assert "access_token" in body


async def test_google_callback_rejects_invalid_state(client: AsyncClient):
    response = await client.get(
        "/api/v1/auth/google/callback",
        params={"code": "fake-code", "state": "not-a-real-state"},
    )

    assert response.status_code == 400


async def test_google_callback_rejects_google_error(client: AsyncClient):
    response = await client.get(
        "/api/v1/auth/google/callback",
        params={"error": "access_denied"},
    )

    assert response.status_code == 400


async def test_google_callback_rejects_existing_email_password_account(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    register_payload = {
        "email": "existing@example.com",
        "password": "Password1!",
        "confirm_password": "Password1!",
        "first_name": "Existing",
        "last_name": "User",
    }
    await client.post("/api/v1/auth/register", json=register_payload)

    state = google_oauth.create_state("test-code-verifier")
    monkeypatch.setattr(
        google_oauth,
        "exchange_code",
        AsyncMock(return_value={"email": register_payload["email"]}),
    )

    response = await client.get(
        "/api/v1/auth/google/callback",
        params={"code": "fake-code", "state": state},
    )

    assert response.status_code == 403
