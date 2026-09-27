import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.repositories import organization_repository
from modules.projects.repositories import project_member_repository, project_repository
from modules.projects.types import ProjectRole


async def _make_user(db_session: AsyncSession, email: str) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Repo",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def _make_project(
    db_session: AsyncSession, owner_id, org_id=None, key="ORB", name="Orbit"
) -> object:
    if org_id is None:
        org = await organization_repository.create_organization(
            db_session, name="Test Org", owner_id=owner_id
        )
        org_id = org.id
    return await project_repository.create_project(
        db_session,
        org_id=org_id,
        key=key,
        name=name,
        description=None,
        owner_id=owner_id,
    )


async def test_add_member_creates_row(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmem-owner1@example.com")
    member = await _make_user(db_session, "pmem-member1@example.com")
    project = await _make_project(db_session, owner.id)

    row = await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=member.id, role=ProjectRole.MEMBER
    )

    assert row.project_id == project.id
    assert row.user_id == member.id
    assert row.role == ProjectRole.MEMBER


async def test_add_member_duplicate_raises_integrity_error(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmem-owner2@example.com")
    member = await _make_user(db_session, "pmem-member2@example.com")
    project = await _make_project(db_session, owner.id)
    await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=member.id, role=ProjectRole.MEMBER
    )

    with pytest.raises(IntegrityError):
        await project_member_repository.add_member(
            db_session, project_id=project.id, user_id=member.id, role=ProjectRole.ADMIN
        )
    await db_session.rollback()


async def test_get_membership_with_user_eager_loads_user(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmem-owner3@example.com")
    project = await _make_project(db_session, owner.id)
    await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=owner.id, role=ProjectRole.OWNER
    )

    result = await project_member_repository.get_membership_with_user(
        db_session, project_id=project.id, user_id=owner.id
    )

    assert result is not None
    assert result.user.email == "pmem-owner3@example.com"


async def test_get_for_project_eager_loads_user_for_each_member(
    db_session: AsyncSession,
):
    owner = await _make_user(db_session, "pmem-owner4@example.com")
    member = await _make_user(db_session, "pmem-member4@example.com")
    project = await _make_project(db_session, owner.id)
    await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=owner.id, role=ProjectRole.OWNER
    )
    await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=member.id, role=ProjectRole.MEMBER
    )

    members, total = await project_member_repository.get_for_project(
        db_session, project_id=project.id, q=None, order=None, limit=20, offset=0
    )

    assert total == 2
    emails = {m.user.email for m in members}
    assert emails == {"pmem-owner4@example.com", "pmem-member4@example.com"}


async def test_get_for_user_eager_loads_project(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmem-owner5@example.com")
    project = await _make_project(db_session, owner.id)
    await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=owner.id, role=ProjectRole.OWNER
    )

    memberships, total = await project_member_repository.get_for_user(
        db_session,
        user_id=owner.id,
        status_filter=None,
        q=None,
        sort=None,
        order=None,
        limit=20,
        offset=0,
    )

    assert total == 1
    assert len(memberships) == 1
    assert memberships[0].project.name == "Orbit"


async def test_get_for_project_search_matches_member_email(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmem-owner-search1@example.com")
    member = await _make_user(db_session, "findme-search1@example.com")
    project = await _make_project(db_session, owner.id)
    await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=owner.id, role=ProjectRole.OWNER
    )
    await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=member.id, role=ProjectRole.MEMBER
    )

    members, total = await project_member_repository.get_for_project(
        db_session, project_id=project.id, q="findme", order=None, limit=20, offset=0
    )

    assert total == 1
    assert members[0].user.email == "findme-search1@example.com"


async def test_get_for_user_search_matches_project_name(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmem-owner-search2@example.com")
    org = await organization_repository.create_organization(
        db_session, name="Org", owner_id=owner.id
    )
    matching = await _make_project(
        db_session, owner.id, org_id=org.id, key="ROC", name="Rocket Launcher"
    )
    other = await _make_project(
        db_session, owner.id, org_id=org.id, key="ACM", name="Acme Widget"
    )
    await project_member_repository.add_member(
        db_session, project_id=matching.id, user_id=owner.id, role=ProjectRole.OWNER
    )
    await project_member_repository.add_member(
        db_session, project_id=other.id, user_id=owner.id, role=ProjectRole.OWNER
    )

    memberships, total = await project_member_repository.get_for_user(
        db_session,
        user_id=owner.id,
        status_filter=None,
        q="rocket",
        sort=None,
        order=None,
        limit=20,
        offset=0,
    )

    assert total == 1
    assert memberships[0].project.name == "Rocket Launcher"


async def test_remove_member_deletes_row(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmem-owner6@example.com")
    member = await _make_user(db_session, "pmem-member6@example.com")
    project = await _make_project(db_session, owner.id)
    await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=member.id, role=ProjectRole.MEMBER
    )

    await project_member_repository.remove_member(
        db_session, project_id=project.id, user_id=member.id
    )

    result = await project_member_repository.get_membership(
        db_session, project_id=project.id, user_id=member.id
    )
    assert result is None


async def test_update_role_persists_new_role(db_session: AsyncSession):
    owner = await _make_user(db_session, "pmem-owner7@example.com")
    member = await _make_user(db_session, "pmem-member7@example.com")
    project = await _make_project(db_session, owner.id)
    row = await project_member_repository.add_member(
        db_session, project_id=project.id, user_id=member.id, role=ProjectRole.MEMBER
    )

    updated = await project_member_repository.update_role(
        db_session, member=row, role=ProjectRole.ADMIN
    )

    assert updated.role == ProjectRole.ADMIN
