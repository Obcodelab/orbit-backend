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


class RealtimeEventType(StrEnum):
    """Broader than ActivityAction — also covers events (presence,
    document indexing, generic task edits/deletes) that never become a
    persisted ActivityLogEntry. Shares string values with ActivityAction
    where the same underlying event applies to both."""

    TASK_CREATED = "task.created"
    TASK_UPDATED = "task.updated"
    TASK_STATUS_CHANGED = "task.status_changed"
    TASK_DELETED = "task.deleted"
    COMMENT_ADDED = "comment.added"
    MEMBER_JOINED = "member.joined"
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_INDEXED = "document.indexed"
    PRESENCE_JOINED = "presence.joined"
    PRESENCE_LEFT = "presence.left"
