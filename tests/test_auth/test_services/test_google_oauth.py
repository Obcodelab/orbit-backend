from datetime import UTC, datetime, timedelta

import jwt

from core.config import settings
from modules.auth.services import google_oauth


def test_create_state_round_trips_code_verifier():
    state = google_oauth.create_state("my-code-verifier")

    assert google_oauth.verify_state(state) == "my-code-verifier"


def test_verify_state_rejects_garbage():
    assert google_oauth.verify_state("not-a-real-state") is None


def test_verify_state_rejects_expired_state():
    now = datetime.now(UTC)
    expired_payload = {
        "purpose": "google_oauth_state",
        "code_verifier": "my-code-verifier",
        "iat": now - timedelta(minutes=10),
        "exp": now - timedelta(minutes=5),
    }
    expired_state = jwt.encode(
        expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )

    assert google_oauth.verify_state(expired_state) is None


def test_verify_state_rejects_token_signed_for_a_different_purpose():
    # A validly-signed token — just not one create_state ever issued.
    now = datetime.now(UTC)
    other_payload = {
        "purpose": "something_else",
        "code_verifier": "my-code-verifier",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    other_token = jwt.encode(
        other_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )

    assert google_oauth.verify_state(other_token) is None


def test_get_authorization_url_points_at_google_with_required_params():
    url = google_oauth.get_authorization_url()

    assert url.startswith("https://accounts.google.com/o/oauth2/auth")
    assert "client_id=" in url
    assert "state=" in url
    assert "scope=" in url
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
