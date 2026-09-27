from enum import StrEnum


class ProjectRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    COMPLETED = "completed"


class ActivityAction(StrEnum):
    TASK_CREATED = "task.created"
    TASK_STATUS_CHANGED = "task.status_changed"
    COMMENT_ADDED = "comment.added"
    MEMBER_JOINED = "member.joined"
