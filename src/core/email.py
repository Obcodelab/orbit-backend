from loguru import logger


def send_email_mock(to: str, subject: str, body: str) -> None:
    """Console-printed stand-in for real email delivery, shared by every
    module — swap this one function out once real delivery exists."""
    logger.info(f"[MOCK EMAIL] To: {to} | Subject: {subject}\n{body}")
