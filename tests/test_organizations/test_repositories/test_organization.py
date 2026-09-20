from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from modules.auth.models import User
from modules.auth.repositories import user_repository
from modules.auth.types import LoginMethod
from modules.organizations.repositories import organization_repository


async def _make_user(
    db_session: AsyncSession, email: str = "org-repo@example.com"
) -> User:
    return await user_repository.create_user(
        db_session,
        email=email,
        first_name="Repo",
        last_name="Test",
        login_method=LoginMethod.EMAIL_PASSWORD,
        password_hash=hash_password("Password1!"),
    )


async def test_create_organization_sets_owner_id(db_session: AsyncSession):
    owner = await _make_user(db_session)

    org = await organization_repository.create_organization(
        db_session, name="Acme Inc", owner_id=owner.id
    )

    assert org.name == "Acme Inc"
    assert org.owner_id == owner.id


async def test_update_name_persists_change(db_session: AsyncSession):
    owner = await _make_user(db_session)
    org = await organization_repository.create_organization(
        db_session, name="Old Name", owner_id=owner.id
    )

    updated = await organization_repository.update_name(
        db_session, org=org, name="New Name"
    )

    assert updated.name == "New Name"
    refetched = await organization_repository.get_by_id(db_session, org.id)
    assert refetched.name == "New Name"
