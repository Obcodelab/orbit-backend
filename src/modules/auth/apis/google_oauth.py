from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from core.dependencies import DBSession
from core.security import create_token_pair
from modules.auth.repositories import user_repository
from modules.auth.schemas import TokenPairResponse
from modules.auth.services import google_oauth, user_service
from modules.auth.types import LoginMethod

google_oauth_router = APIRouter()


@google_oauth_router.get("/login")
async def google_login() -> RedirectResponse:
    auth_url = google_oauth.get_authorization_url()
    return RedirectResponse(auth_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@google_oauth_router.get("/callback")
async def google_callback(
    session: DBSession,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> TokenPairResponse:
    if error:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Google sign-in was not completed: {error}"
        )

    code_verifier = google_oauth.verify_state(state) if state else None
    if not code or not code_verifier:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid or expired sign-in attempt"
        )

    id_info = await google_oauth.exchange_code(code, code_verifier)
    email = id_info["email"]

    existing = await user_repository.get_by_email(session, email)
    if existing and existing.login_method != LoginMethod.GOOGLE:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "An account with this email already exists using a different "
            "sign-in method",
        )

    user, _ = await user_repository.get_or_create_google_user(
        session,
        email=email,
        first_name=id_info.get("given_name") or email.split("@")[0],
        last_name=id_info.get("family_name") or "",
        profile_picture=id_info.get("picture"),
    )

    token_pair = create_token_pair({"sub": str(user.id)})
    return TokenPairResponse(**token_pair, user=user_service.build_response(user))
