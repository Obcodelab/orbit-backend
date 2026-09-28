import hashlib
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from core.config import settings
from core.exceptions import TokenExpiredError, TokenInvalidError
from core.pagination import Page
from core.security import decode_token
from core.types import SortOrder, TokenType
from modules.files.exceptions import (
    DocumentNotFoundError,
    FileTooLargeError,
    InvalidDownloadTokenError,
    NotDocumentUploaderError,
    UnsupportedFileTypeError,
)
from modules.files.models import Document
from modules.files.repositories import DocumentRepository, document_repository
from modules.files.schemas import DocumentResponse, DownloadUrlResponse
from modules.files.storage import StorageBackend
from modules.projects.exceptions import ProjectArchivedError
from modules.projects.models import Project, ProjectMember
from modules.projects.types import ProjectRole, ProjectStatus
from modules.tasks.exceptions import ParentTaskNotFoundError
from modules.tasks.repositories import TaskRepository, task_repository


class DocumentService:
    def __init__(
        self, document_repo: DocumentRepository, task_repo: TaskRepository
    ) -> None:
        self.document_repo = document_repo
        self.task_repo = task_repo

    async def upload_document(
        self,
        session: AsyncSession,
        *,
        project: Project,
        task_id: UUID | None,
        uploader_id: UUID,
        filename: str,
        file_bytes: bytes,
        mime_type: str,
        storage_backend: StorageBackend,
    ) -> tuple[Document, UUID | None]:
        """Returns the new document plus, when its content matches an
        existing document in this project, that document's id — the
        caller can then reuse its embeddings instead of re-ingesting."""
        if project.status == ProjectStatus.ARCHIVED:
            raise ProjectArchivedError

        file_size = len(file_bytes)
        if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise FileTooLargeError
        if mime_type not in settings.ALLOWED_FILE_TYPES:
            raise UnsupportedFileTypeError

        if task_id is not None:
            task = await self.task_repo.get_scoped(
                session, project_id=project.id, task_id=task_id
            )
            if not task:
                raise ParentTaskNotFoundError

        content_hash = hashlib.sha256(file_bytes).hexdigest()
        existing = await self.document_repo.get_one_by_content_hash(
            session, project_id=project.id, content_hash=content_hash
        )

        document_id = uuid7()
        if existing is not None:
            storage_path = existing.storage_path
        else:
            path = f"{project.id}/{document_id}/{filename}"
            storage_path = await storage_backend.save(file_bytes=file_bytes, path=path)

        document = await self.document_repo.create_document(
            session,
            id=document_id,
            org_id=project.org_id,
            project_id=project.id,
            task_id=task_id,
            uploader_id=uploader_id,
            filename=filename,
            file_size=file_size,
            mime_type=mime_type,
            storage_path=storage_path,
            content_hash=content_hash,
        )
        return document, (existing.id if existing is not None else None)

    async def list_for_project(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        order: SortOrder | None,
        limit: int,
        offset: int,
    ) -> Page[DocumentResponse]:
        documents, total = await self.document_repo.get_for_project(
            session, project_id=project_id, order=order, limit=limit, offset=offset
        )
        items = [DocumentResponse.model_validate(d) for d in documents]
        return Page(items=items, total=total, limit=limit, offset=offset)

    async def get_document(
        self, session: AsyncSession, *, project_id: UUID, document_id: UUID
    ) -> Document:
        document = await self.document_repo.get_scoped(
            session, project_id=project_id, document_id=document_id
        )
        if not document:
            raise DocumentNotFoundError
        return document

    async def get_download_url(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        document_id: UUID,
        storage_backend: StorageBackend,
    ) -> DownloadUrlResponse:
        document = await self.get_document(
            session, project_id=project_id, document_id=document_id
        )
        url = await storage_backend.get_download_url(
            path=document.storage_path, project_id=project_id, document_id=document_id
        )
        return DownloadUrlResponse(url=url)

    def resolve_download_token(self, token: str) -> UUID:
        try:
            claims = decode_token(token)
        except (TokenExpiredError, TokenInvalidError) as exc:
            raise InvalidDownloadTokenError from exc
        if claims.get("type") != TokenType.DOWNLOAD:
            raise InvalidDownloadTokenError
        raw_document_id = claims.get("document_id")
        if not raw_document_id:
            raise InvalidDownloadTokenError
        return UUID(raw_document_id)

    async def delete_document(
        self,
        session: AsyncSession,
        *,
        project: Project,
        document_id: UUID,
        caller: ProjectMember,
    ) -> str | None:
        """Deletes the row and returns its storage path only if no other
        document still shares it (dedup can leave several pointing at
        the same file) — caller must defer the storage delete until
        this transaction commits, since an unlink can't be rolled back."""
        if project.status == ProjectStatus.ARCHIVED:
            raise ProjectArchivedError

        document = await self.get_document(
            session, project_id=project.id, document_id=document_id
        )
        is_privileged = caller.role in (ProjectRole.OWNER, ProjectRole.ADMIN)
        if not is_privileged and document.uploader_id != caller.user_id:
            raise NotDocumentUploaderError

        await self.document_repo.lock_storage_path(session, document.storage_path)
        await self.document_repo.delete_by_id(session, document.id)
        remaining = await self.document_repo.count_by_storage_path(
            session, storage_path=document.storage_path, exclude_id=document.id
        )
        return document.storage_path if remaining == 0 else None


document_service = DocumentService(
    document_repo=document_repository, task_repo=task_repository
)
