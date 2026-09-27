class TaskNotFoundError(Exception):
    """No task exists with this id within this project."""


class AssigneeNotProjectMemberError(Exception):
    """An assignee must already be a member of the project being
    assigned to — same reasoning as project membership requiring org
    membership first."""


class StatusChangeForbiddenError(Exception):
    """Only the task's own assignees or a project admin/owner can move
    its status; everything else is admin/owner-only."""


class ParentTaskNotFoundError(Exception):
    """The given parent_task_id doesn't exist within this project."""


class CommentNotFoundError(Exception):
    """No comment exists with this id on this task."""


class NotCommentAuthorError(Exception):
    """Only the comment's own author can update or delete it."""
