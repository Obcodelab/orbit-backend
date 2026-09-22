class NotOrgMemberError(Exception):
    """The target user isn't a member of the project's organization —
    project membership is only ever granted to people already in the org."""


class InsufficientOrgRoleError(Exception):
    """The caller is an org member but not an owner/admin — creating a
    project is an org-level action gated the same way inviting members is."""


class AlreadyProjectMemberError(Exception):
    """The target user already belongs to this project."""


class ProjectMembershipNotFoundError(Exception):
    """The target user isn't a member of this project."""


class CannotRemoveProjectOwnerError(Exception):
    """The project's owner can't be removed — same reasoning as
    organizations: no ownership-transfer flow to fall back on."""


class CannotChangeProjectOwnerRoleError(Exception):
    """The project's owner's role can't be changed — same reasoning as
    removal."""


class DuplicateProjectKeyError(Exception):
    """This org already has a project using this key."""


class ProjectArchivedError(Exception):
    """The action is blocked because the project is archived — read-only
    except for the un-archiving PATCH itself."""
