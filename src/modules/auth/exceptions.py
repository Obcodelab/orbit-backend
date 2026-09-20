class VerificationCooldownError(Exception):
    """A code was already sent too recently — only raised for the explicit
    resend endpoint, never for register's initial send or login's
    auto-resend-on-unverified, which stay silent."""

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
