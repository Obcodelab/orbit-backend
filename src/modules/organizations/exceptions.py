class AlreadyMemberError(Exception):
    """The invited user already belongs to this organization."""


class AlreadyInvitedError(Exception):
    """A pending invite already exists for this user in this organization."""


class InviteNotFoundError(Exception):
    """No pending invite matches this id (wrong id, already resolved, or
    belongs to someone else / a different organization)."""


class MembershipNotFoundError(Exception):
    """The target user isn't a member of this organization."""


class CannotRemoveOwnerError(Exception):
    """The org's owner can't be removed without an ownership transfer,
    which doesn't exist yet — removing them would leave the org ownerless."""


class CannotChangeOwnerRoleError(Exception):
    """The org's owner's role can't be changed — same reason as removal:
    no ownership-transfer flow exists to fall back on."""
