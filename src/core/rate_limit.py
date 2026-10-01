from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from core.config import settings
from core.exceptions import TokenExpiredError, TokenInvalidError
from core.security import decode_token
from core.types import TokenType


def get_rate_limit_key(request: Request) -> str:
    """Keys by user id when possible, so a shared network doesn't share
    one quota — falls back to remote address for unauthenticated routes.
    Decodes the JWT directly rather than via get_current_user, so this
    stays a cheap local check, not a DB-backed auth decision."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ")
        try:
            claims = decode_token(token)
            if claims.get("type") == TokenType.ACCESS and claims.get("sub"):
                return f"user:{claims['sub']}"
        except (TokenExpiredError, TokenInvalidError):
            pass
    return get_remote_address(request)


# In-memory storage, not Redis — no other Redis dependency exists yet in
# this project, and single-process scale doesn't need it. Same reasoning
# as the auth token blacklist's lack of a cache layer.
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
)
