from enum import StrEnum


class ProjectRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    COMPLETED = "completed"
