from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)

from core.config import settings
from core.dependencies import AuthenticatedUser, DBSession, PaginationParams
from core.pagination import Page
from core.rate_limit import limiter
from core.types import RealtimeEventType, SortOrder
from core.websocket_manager import build_event, connection_manager
from modules.ai.services import ingestion_service
from modules.files.dependencies import StorageBackendDep
from modules.files.exceptions import (
    DocumentNotFoundError,
    FileTooLargeError,
    NotDocumentUploaderError,
    UnsupportedFileTypeError,
)
from modules.files.schemas import DocumentResponse, DownloadUrlResponse
from modules.files.services import document_service
from modules.projects.dependencies import AnyProjectMember
from modules.projects.exceptions import ProjectArchivedError
from modules.projects.repositories import project_repository
from modules.tasks.exceptions import ParentTaskNotFoundError

document_router = APIRouter(tags=["Documents"])

upload_rate_limit = limiter.limit(settings.RATE_LIMIT_UPLOAD)


@document_router.post(
    "/projects/{project_id}/documents", status_code=status.HTTP_201_CREATED
)
@upload_rate_limit
async def upload_document(
    request: Request,
    project_id: UUID,
    user: AuthenticatedUser,
    session: DBSession,
    membership: AnyProjectMember,
    background_tasks: BackgroundTasks,
    storage_backend: StorageBackendDep,
    file: UploadFile = File(...),
    task_id: UUID | None = Form(default=None),
) -> DocumentResponse:
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A filename is required")

    project = await project_repository.get_by_id(session, project_id)
    file_bytes = await file.read()
    try:
        document, dedup_source_id = await document_service.upload_document(
            session,
            project=project,
            task_id=task_id,
            uploader_id=user.id,
            filename=file.filename,
            file_bytes=file_bytes,
            mime_type=file.content_type or "application/octet-stream",
            storage_backend=storage_backend,
        )
    except ProjectArchivedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This project is archived and is read-only"
        )
    except FileTooLargeError:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"File exceeds the {settings.MAX_FILE_SIZE_MB}MB limit",
        )
    except UnsupportedFileTypeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File type not allowed")
    except ParentTaskNotFoundError:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "task_id doesn't exist in this project"
        )

    response = DocumentResponse.model_validate(document)
    await connection_manager.broadcast(
        project_id,
        build_event(
            event_type=RealtimeEventType.DOCUMENT_UPLOADED,
            project_id=project_id,
            data=response.model_dump(mode="json"),
            actor_id=user.id,
        ),
    )
    if dedup_source_id is not None:
        background_tasks.add_task(
            ingestion_service.clone_or_ingest,
            document_id=document.id,
            source_document_id=dedup_source_id,
        )
    else:
        background_tasks.add_task(
            ingestion_service.ingest_document, document_id=document.id
        )
    return response


@document_router.get("/projects/{project_id}/documents")
async def list_documents(
    project_id: UUID,
    session: DBSession,
    membership: AnyProjectMember,
    pagination: PaginationParams,
    order: SortOrder | None = Query(default=None),
) -> Page[DocumentResponse]:
    return await document_service.list_for_project(
        session,
        project_id=project_id,
        order=order,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@document_router.get("/projects/{project_id}/documents/{document_id}")
async def get_document(
    project_id: UUID,
    document_id: UUID,
    session: DBSession,
    membership: AnyProjectMember,
) -> DocumentResponse:
    try:
        document = await document_service.get_document(
            session, project_id=project_id, document_id=document_id
        )
    except DocumentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return DocumentResponse.model_validate(document)


@document_router.get("/projects/{project_id}/documents/{document_id}/download")
async def get_document_download_url(
    project_id: UUID,
    document_id: UUID,
    session: DBSession,
    membership: AnyProjectMember,
    storage_backend: StorageBackendDep,
) -> DownloadUrlResponse:
    try:
        return await document_service.get_download_url(
            session,
            project_id=project_id,
            document_id=document_id,
            storage_backend=storage_backend,
        )
    except DocumentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")


@document_router.delete(
    "/projects/{project_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    project_id: UUID,
    document_id: UUID,
    session: DBSession,
    membership: AnyProjectMember,
    background_tasks: BackgroundTasks,
    storage_backend: StorageBackendDep,
) -> None:
    project = await project_repository.get_by_id(session, project_id)
    try:
        storage_path = await document_service.delete_document(
            session,
            project=project,
            document_id=document_id,
            caller=membership,
        )
    except ProjectArchivedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This project is archived and is read-only"
        )
    except DocumentNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    except NotDocumentUploaderError:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the uploader or a project admin/owner can delete this document",
        )

    if storage_path is not None:
        background_tasks.add_task(storage_backend.delete, storage_path)
