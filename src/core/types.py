from enum import StrEnum


class Environment(StrEnum):
    LOCAL = "local"
    PROD = "prod"


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    RESET = "reset"
