from enum import StrEnum


class LoginMethod(StrEnum):
    EMAIL_PASSWORD = "email_password"
    GOOGLE = "google"


class VerificationPurpose(StrEnum):
    EMAIL_VERIFICATION = "email_verification"
    PASSWORD_RESET = "password_reset"
