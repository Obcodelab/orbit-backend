from sqlalchemy.ext.asyncio import AsyncSession

from core.repository import BaseRepository
from modules.auth.models import User
from modules.auth.types import LoginMethod


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        return await self.get_by(session, email=email)

    async def create_user(
        self,
        session: AsyncSession,
        *,
        email: str,
        first_name: str,
        last_name: str,
        login_method: LoginMethod,
        password_hash: str | None = None,
        profile_picture: str | None = None,
        email_verified: bool = False,
    ) -> User:
        return await self.create(
            session,
            email=email,
            first_name=first_name,
            last_name=last_name,
            login_method=login_method,
            password_hash=password_hash,
            profile_picture=profile_picture,
            email_verified=email_verified,
        )

    async def get_or_create_google_user(
        self,
        session: AsyncSession,
        *,
        email: str,
        first_name: str,
        last_name: str,
        profile_picture: str | None,
    ) -> tuple[User, bool]:
        user = await self.get_by_email(session, email)
        if user:
            return user, False

        new_user = await self.create_user(
            session,
            email=email,
            first_name=first_name,
            last_name=last_name,
            login_method=LoginMethod.GOOGLE,
            email_verified=True,
            profile_picture=profile_picture,
        )
        return new_user, True

    async def set_email_verified(self, session: AsyncSession, user: User) -> User:
        user.email_verified = True
        return await self.flush_and_refresh(session, user)

    async def update_password(
        self, session: AsyncSession, *, user: User, hashed_password: str
    ) -> User:
        user.password_hash = hashed_password
        return await self.flush_and_refresh(session, user)

    async def update_profile(
        self, session: AsyncSession, *, user: User, updates: dict
    ) -> User:
        for field, value in updates.items():
            setattr(user, field, value)
        return await self.flush_and_refresh(session, user)


user_repository = UserRepository()
