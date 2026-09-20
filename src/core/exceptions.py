class TokenExpiredError(Exception):
    """A JWT's exp claim is in the past."""


class TokenInvalidError(Exception):
    """A JWT failed signature verification or is otherwise malformed."""
