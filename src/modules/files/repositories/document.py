from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.repository import BaseRepository
from core.types import SortOrder
from modules.files.models import Document


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def create_document(
        self,
        session: AsyncSession,
        *,
        id: UUID,
        org_id: UUID,
        project_id: UUID,
        task_id: UUID | None,
        uploader_id: UUID,
        filename: str,
        file_size: int,
        mime_type: str,
        storage_path: str,
        content_hash: str,
    ) -> Document:
        return await self.create(
            session,
            id=id,
            org_id=org_id,
            project_id=project_id,
            task_id=task_id,
            uploader_id=uploader_id,
            filename=filename,
            file_size=file_size,
            mime_type=mime_type,
            storage_path=storage_path,
            content_hash=content_hash,
        )

    async def get_scoped(
        self, session: AsyncSession, *, project_id: UUID, document_id: UUID
    ) -> Document | None:
        return await self.get_by(session, id=document_id, project_id=project_id)

    async def get_one_by_content_hash(
        self, session: AsyncSession, *, project_id: UUID, content_hash: str
    ) -> Document | None:
        """More than one document can share a hash once dedup reuses
        storage across uploads, so this can't use the generic get_by
        (which errors on multiple matches) — any one match is enough."""
        stmt = (
            select(self.model)
            .where(
                self.model.project_id == project_id,
                self.model.content_hash == content_hash,
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_by_storage_path(
        self, session: AsyncSession, *, storage_path: str, exclude_id: UUID
    ) -> int:
        stmt = select(func.count()).where(
            self.model.storage_path == storage_path, self.model.id != exclude_id
        )
        result = await session.execute(stmt)
        return result.scalar_one()

    async def lock_storage_path(self, session: AsyncSession, storage_path: str) -> None:
        """Postgres advisory lock scoped to this transaction, keyed on the
        path — serializes concurrent deletes of documents that share
        storage so they don't both see each other as "still referenced"
        and leak the file. Released automatically on commit/rollback."""
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:path))"),
            {"path": storage_path},
        )

    async def get_for_project(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Document], int]:
        stmt = select(self.model).where(self.model.project_id == project_id)
        total = await self._count(session, stmt)
        stmt = self._apply_order(
            stmt,
            order=order,
            column=self.model.created_at,
            default_order=SortOrder.DESC,
        )
        stmt = stmt.limit(limit).offset(offset)
        result = await session.execute(stmt)
        return list(result.scalars().all()), total


document_repository = DocumentRepository()
