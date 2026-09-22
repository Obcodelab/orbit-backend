from typing import Annotated

from fastapi import Depends

from core.dependencies import require_project_role
from modules.projects.models import ProjectMember
from modules.projects.types import ProjectRole

AnyProjectMember = Annotated[ProjectMember, Depends(require_project_role(*ProjectRole))]
ProjectAdminOrOwner = Annotated[
    ProjectMember,
    Depends(require_project_role(ProjectRole.OWNER, ProjectRole.ADMIN)),
]
ProjectOwnerOnly = Annotated[
    ProjectMember, Depends(require_project_role(ProjectRole.OWNER))
]
