from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password, verify_password
from modules.auth.models import User
from modules.auth.repositories import UserRepository, user_repository
from modules.auth.schemas.user import UserResponse
from modules.auth.types import LoginMethod


class UserService:
    def __init__(self, user_repo: UserRepository) -> None:
        self.user_repo = user_repo

    async def register(
        self,
        session: AsyncSession,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
    ) -> User:
        return await self.user_repo.create_user(
            session,
            email=email,
            first_name=first_name,
            last_name=last_name,
            login_method=LoginMethod.EMAIL_PASSWORD,
            password_hash=hash_password(password),
        )

    def verify_credentials(self, user: User, password: str) -> bool:
        if not user.password_hash:
            return False
        return verify_password(password, user.password_hash)

    async def change_password(
        self,
        session: AsyncSession,
        *,
        user: User,
        current_password: str,
        new_password: str,
    ) -> None:
        if not user.password_hash or not verify_password(
            current_password, user.password_hash
        ):
            raise ValueError("Current password is incorrect")
        await self.user_repo.update_password(
            session, user=user, hashed_password=hash_password(new_password)
        )

    async def reset_password(
        self, session: AsyncSession, *, user: User, new_password: str
    ) -> None:
        await self.user_repo.update_password(
            session, user=user, hashed_password=hash_password(new_password)
        )

    async def update_profile(
        self, session: AsyncSession, *, user: User, updates: dict
    ) -> User:
        return await self.user_repo.update_profile(session, user=user, updates=updates)

    def build_response(self, user: User) -> UserResponse:
        return UserResponse.model_validate(user)


user_service = UserService(user_repo=user_repository)
