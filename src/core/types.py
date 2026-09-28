from enum import StrEnum


class Environment(StrEnum):
    LOCAL = "local"
    PROD = "prod"


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    RESET = "reset"
    DOWNLOAD = "download"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class NameSort(StrEnum):
    """Shared sort-field enum for "my orgs"/"my projects" style lists,
    which also support sorting by the resource's own name."""

    CREATED_AT = "created_at"
    NAME = "name"
