"""Authorization-code exchange for Google sign-in. The backend owns the
redirect round trip via google-auth-oauthlib rather than verifying a
frontend-supplied ID token — chosen because there's no frontend yet to
embed Google's Identity Services SDK."""

import asyncio
import base64
import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from google_auth_oauthlib.flow import Flow

from core.config import settings

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

_SCOPES = ["openid", "email", "profile"]
_STATE_PURPOSE = "google_oauth_state"


def _build_flow(*, state: str | None = None) -> Flow:
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_SIGNIN_CLIENT_ID,
                "client_secret": settings.GOOGLE_SIGNIN_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=_SCOPES,
        state=state,
        redirect_uri=settings.GOOGLE_SIGNIN_REDIRECT_URI,
    )


def _generate_pkce_pair() -> tuple[str, str]:
    """RFC 7636 PKCE — Google now requires this on the authorization-code
    flow (a bare code is no longer enough). The verifier has to survive the
    round trip to Google and back with no server-side session to hold it,
    so it travels inside the signed `state` JWT instead."""
    code_verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


def create_state(code_verifier: str) -> str:
    """A short-lived signed nonce, not a value stored server-side — its
    signature alone proves this backend initiated the login being
    completed. Also carries the PKCE code_verifier across the redirect."""
    now = datetime.now(UTC)
    payload = {
        "purpose": _STATE_PURPOSE,
        "code_verifier": code_verifier,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def verify_state(state: str) -> str | None:
    """Returns the embedded PKCE code_verifier if `state` is a valid,
    unexpired token this backend issued — None otherwise."""
    try:
        claims = jwt.decode(
            state, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.InvalidTokenError:
        return None
    if claims.get("purpose") != _STATE_PURPOSE:
        return None
    return claims.get("code_verifier")


def get_authorization_url() -> str:
    code_verifier, code_challenge = _generate_pkce_pair()
    state = create_state(code_verifier)
    flow = _build_flow(state=state)
    auth_url, _ = flow.authorization_url(
        access_type="online",
        include_granted_scopes="true",
        prompt="select_account",
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    return auth_url


def _exchange_code_sync(code: str, code_verifier: str) -> dict[str, Any]:
    flow = _build_flow()
    flow.fetch_token(code=code, code_verifier=code_verifier)
    id_token_str = flow.credentials.id_token
    return google_id_token.verify_oauth2_token(
        id_token_str, google_requests.Request(), settings.GOOGLE_SIGNIN_CLIENT_ID
    )


async def exchange_code(code: str, code_verifier: str) -> dict[str, Any]:
    """Exchanges an authorization code for Google's tokens (blocking —
    google-auth-oauthlib uses `requests`, not an async client) and returns
    the verified ID token's claims."""
    return await asyncio.to_thread(_exchange_code_sync, code, code_verifier)
