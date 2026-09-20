from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import BaseModel


class BaseRepository[T: BaseModel]:
    """Generic CRUD shared by every entity repository. Entity repositories
    add only what's actually specific to that entity."""

    model: type[T]

    async def get_by_id(self, session: AsyncSession, id: UUID) -> T | None:
        return await session.get(self.model, id)

    async def get_by_ids(self, session: AsyncSession, ids: list[UUID]) -> list[T]:
        stmt = select(self.model).where(self.model.id.in_(ids))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by(self, session: AsyncSession, **filters) -> T | None:
        stmt = select(self.model)
        for field, value in filters.items():
            stmt = stmt.where(getattr(self.model, field) == value)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by(self, session: AsyncSession, **filters) -> list[T]:
        stmt = select(self.model)
        for field, value in filters.items():
            stmt = stmt.where(getattr(self.model, field) == value)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    def add(self, session: AsyncSession, instance: T) -> None:
        session.add(instance)

    async def add_and_flush(self, session: AsyncSession, instance: T) -> T:
        self.add(session, instance)
        await session.flush()
        return instance

    async def flush_and_refresh(self, session: AsyncSession, instance: T) -> T:
        await self.add_and_flush(session, instance)
        await session.refresh(instance)
        return instance

    async def add_and_flush_instances(
        self, session: AsyncSession, instances: list[T]
    ) -> list[T]:
        for instance in instances:
            self.add(session, instance)
        await session.flush()
        return instances

    async def flush_and_refresh_instances(
        self, session: AsyncSession, instances: list[T]
    ) -> list[T]:
        await self.add_and_flush_instances(session, instances)
        for instance in instances:
            await session.refresh(instance)
        return instances

    async def create(self, session: AsyncSession, **kwargs) -> T:
        instance = self.model(**kwargs)
        return await self.flush_and_refresh(session, instance)

    async def create_instances(
        self, session: AsyncSession, kwargs_list: list[dict]
    ) -> list[T]:
        instances = [self.model(**kwargs) for kwargs in kwargs_list]
        return await self.flush_and_refresh_instances(session, instances)

    async def delete_by_id(self, session: AsyncSession, id: UUID) -> bool:
        stmt = delete(self.model).where(self.model.id == id)
        result = await session.execute(stmt)
        return result.rowcount > 0  # type: ignore[attr-defined]

    async def delete_by_ids(self, session: AsyncSession, ids: list[UUID]) -> int:
        stmt = delete(self.model).where(self.model.id.in_(ids))
        result = await session.execute(stmt)
        return result.rowcount  # type: ignore[attr-defined]

    async def delete_by(self, session: AsyncSession, **filters) -> int:
        stmt = delete(self.model)
        for field, value in filters.items():
            stmt = stmt.where(getattr(self.model, field) == value)
        result = await session.execute(stmt)
        return result.rowcount  # type: ignore[attr-defined]
