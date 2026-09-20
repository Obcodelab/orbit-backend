from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from core.config import settings
from core.dependencies import AuthenticatedUser, DBSession
from core.exceptions import TokenExpiredError, TokenInvalidError
from core.rate_limit import limiter
from core.security import (
    create_access_token,
    create_reset_token,
    create_token_pair,
    decode_token,
)
from core.types import TokenType
from modules.auth.exceptions import VerificationCooldownError
from modules.auth.repositories import user_repository, verification_code_repository
from modules.auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshResponse,
    RefreshTokenRequest,
    RegisterRequest,
    ResendCodeRequest,
    ResetPasswordRequest,
    ResetTokenResponse,
    TokenPairResponse,
    UserResponse,
    UserUpdateRequest,
    VerifyEmailRequest,
    VerifyResetCodeRequest,
)
from modules.auth.services import blacklist_service, user_service, verification_service
from modules.auth.types import LoginMethod, VerificationPurpose

user_router = APIRouter()
profile_router = APIRouter()

auth_rate_limit = limiter.limit(settings.RATE_LIMIT_AUTH)


@user_router.post("/register", status_code=status.HTTP_201_CREATED)
@auth_rate_limit
async def register(
    request: Request, body: RegisterRequest, session: DBSession
) -> MessageResponse:
    if await user_repository.get_by_email(session, body.email):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "User with this email already exists"
        )

    user = await user_service.register(
        session,
        email=body.email,
        password=body.password,
        first_name=body.first_name,
        last_name=body.last_name,
    )
    await verification_service.send_email_verification_code(session, user)

    return MessageResponse(
        detail="Account created — check your email for a verification code."
    )


@user_router.post("/login")
@auth_rate_limit
async def login(
    request: Request, body: LoginRequest, session: DBSession
) -> TokenPairResponse | MessageResponse:
    invalid_credentials = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Invalid credentials"
    )

    user = await user_repository.get_by_email(session, body.email)
    if not user:
        raise invalid_credentials

    if user.login_method != LoginMethod.EMAIL_PASSWORD:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This account uses a different sign-in method"
        )

    if not user_service.verify_credentials(user, body.password):
        raise invalid_credentials

    if not user.email_verified:
        await verification_service.send_email_verification_code(session, user)
        return MessageResponse(
            detail="Email not verified — a new verification code has been sent."
        )

    token_pair = create_token_pair({"sub": str(user.id)})
    return TokenPairResponse(**token_pair, user=user_service.build_response(user))


@user_router.post("/verify-email")
@auth_rate_limit
async def verify_email(
    request: Request, body: VerifyEmailRequest, session: DBSession
) -> TokenPairResponse:
    user = await user_repository.get_by_email(session, body.email)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    verified = await verification_service.verify_code(
        session,
        user_id=user.id,
        code=body.code,
        purpose=VerificationPurpose.EMAIL_VERIFICATION,
    )
    if not verified:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Invalid or expired verification code"
        )

    user = await user_repository.set_email_verified(session, user)
    token_pair = create_token_pair({"sub": str(user.id)})
    return TokenPairResponse(**token_pair, user=user_service.build_response(user))


@user_router.post("/resend-code")
@auth_rate_limit
async def resend_code(
    request: Request, body: ResendCodeRequest, session: DBSession
) -> MessageResponse:
    generic_response = MessageResponse(
        detail="If an account exists for that email, a code has been sent."
    )

    user = await user_repository.get_by_email(session, body.email)
    if not user or user.login_method != LoginMethod.EMAIL_PASSWORD:
        return generic_response

    latest = await verification_code_repository.get_latest_for_user(
        session, user_id=user.id
    )
    if not latest:
        return generic_response  # nothing outstanding — nothing to infer

    purpose = latest.purpose
    if purpose == VerificationPurpose.EMAIL_VERIFICATION and user.email_verified:
        return generic_response

    try:
        await verification_service.check_resend_cooldown(
            session, user_id=user.id, purpose=purpose
        )
    except VerificationCooldownError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Please wait {exc.retry_after_seconds} seconds before "
            "requesting another code.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

    await verification_service.send_code(session, user, purpose)
    return generic_response


@user_router.post("/refresh")
async def refresh(body: RefreshTokenRequest, session: DBSession) -> RefreshResponse:
    invalid = HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid refresh token")

    try:
        claims = decode_token(body.refresh_token)
    except (TokenExpiredError, TokenInvalidError):
        raise invalid

    if claims.get("type") != TokenType.REFRESH:
        raise invalid

    raw_jti = claims.get("jti")
    if not raw_jti or await blacklist_service.is_blacklisted(session, UUID(raw_jti)):
        raise invalid

    raw_user_id = claims.get("sub")
    user = (
        await user_repository.get_by_id(session, UUID(raw_user_id))
        if raw_user_id
        else None
    )
    if not user or not user.is_active:
        raise invalid

    access_token, access_expires_at = create_access_token({"sub": str(user.id)})
    return RefreshResponse(
        access_token=access_token, access_expires_at=access_expires_at
    )


@user_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request, body: LogoutRequest, user: AuthenticatedUser, session: DBSession
) -> None:
    invalid = HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid refresh token")

    try:
        refresh_claims = decode_token(body.refresh_token)
    except (TokenExpiredError, TokenInvalidError):
        raise invalid

    if refresh_claims.get("type") != TokenType.REFRESH:
        raise invalid

    access_token: str = request.state.access_token
    access_jti: UUID = request.state.access_jti
    access_claims = decode_token(access_token)

    await blacklist_service.blacklist_token(
        session,
        jti=access_jti,
        token_type=TokenType.ACCESS,
        expires_at=datetime.fromtimestamp(access_claims["exp"], tz=UTC),
    )
    await blacklist_service.blacklist_token(
        session,
        jti=UUID(refresh_claims["jti"]),
        token_type=TokenType.REFRESH,
        expires_at=datetime.fromtimestamp(refresh_claims["exp"], tz=UTC),
    )
    await blacklist_service.cleanup_expired(session)


@user_router.post("/forgot-password")
@auth_rate_limit
async def forgot_password(
    request: Request, body: ForgotPasswordRequest, session: DBSession
) -> MessageResponse:
    generic_response = MessageResponse(
        detail="If an account exists for that email, a password reset code "
        "has been sent."
    )

    user = await user_repository.get_by_email(session, body.email)
    if user and user.login_method == LoginMethod.EMAIL_PASSWORD:
        await verification_service.send_password_reset_code(session, user)

    return generic_response


@user_router.post("/verify-reset-code")
@auth_rate_limit
async def verify_reset_code(
    request: Request, body: VerifyResetCodeRequest, session: DBSession
) -> ResetTokenResponse:
    invalid_code = HTTPException(
        status.HTTP_400_BAD_REQUEST, "Invalid or expired verification code"
    )

    user = await user_repository.get_by_email(session, body.email)
    if not user:
        raise invalid_code

    verified = await verification_service.verify_code(
        session,
        user_id=user.id,
        code=body.code,
        purpose=VerificationPurpose.PASSWORD_RESET,
    )
    if not verified:
        raise invalid_code

    reset_token, _ = create_reset_token({"sub": str(user.id)})
    return ResetTokenResponse(reset_token=reset_token)


@user_router.post("/reset-password")
@auth_rate_limit
async def reset_password(
    request: Request, body: ResetPasswordRequest, session: DBSession
) -> MessageResponse:
    invalid = HTTPException(
        status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token"
    )

    try:
        claims = decode_token(body.reset_token)
    except (TokenExpiredError, TokenInvalidError):
        raise invalid

    if claims.get("type") != TokenType.RESET:
        raise invalid

    raw_jti = claims.get("jti")
    if not raw_jti:
        raise invalid
    jti = UUID(raw_jti)

    if await blacklist_service.is_blacklisted(session, jti):
        raise invalid

    raw_user_id = claims.get("sub")
    user = (
        await user_repository.get_by_id(session, UUID(raw_user_id))
        if raw_user_id
        else None
    )
    if not user:
        raise invalid

    await user_service.reset_password(
        session, user=user, new_password=body.new_password
    )

    await blacklist_service.blacklist_token(
        session,
        jti=jti,
        token_type=TokenType.RESET,
        expires_at=datetime.fromtimestamp(claims["exp"], tz=UTC),
    )

    return MessageResponse(detail="Password reset successfully")


@profile_router.post("/change-password")
@auth_rate_limit
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    user: AuthenticatedUser,
    session: DBSession,
) -> MessageResponse:
    if not user.password_hash:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Password change is not available for this account",
        )

    try:
        await user_service.change_password(
            session,
            user=user,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    return MessageResponse(detail="Password changed successfully")


@profile_router.get("/me")
async def get_me(user: AuthenticatedUser) -> UserResponse:
    return user_service.build_response(user)


@profile_router.patch("/me")
async def update_me(
    body: UserUpdateRequest, user: AuthenticatedUser, session: DBSession
) -> UserResponse:
    updates = body.model_dump(exclude_none=True)
    updated_user = await user_service.update_profile(
        session, user=user, updates=updates
    )
    return user_service.build_response(updated_user)
