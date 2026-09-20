from slowapi import Limiter
from slowapi.util import get_remote_address

from core.config import settings

# In-memory storage, not Redis — no other Redis dependency exists yet in
# this project, and single-process scale doesn't need it. Same reasoning
# as the auth token blacklist's lack of a cache layer.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
)
