from typing import Annotated

from fastapi import Depends

from core.dependencies import require_role
from modules.organizations.models import OrganizationMember
from modules.organizations.types import OrganizationRole

AnyMember = Annotated[OrganizationMember, Depends(require_role(*OrganizationRole))]
AdminOrOwner = Annotated[
    OrganizationMember,
    Depends(require_role(OrganizationRole.OWNER, OrganizationRole.ADMIN)),
]
OwnerOnly = Annotated[OrganizationMember, Depends(require_role(OrganizationRole.OWNER))]
