from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from core.dependencies import DBSession
from modules.files.dependencies import StorageBackendDep
from modules.files.exceptions import InvalidDownloadTokenError
from modules.files.repositories import document_repository
from modules.files.services import document_service
from modules.files.storage import LocalStorageBackend

download_router = APIRouter(tags=["Documents"])


@download_router.get("/files/download")
async def download_by_token(
    session: DBSession, storage_backend: StorageBackendDep, token: str = Query(...)
) -> FileResponse:
    """Unauthenticated by Bearer token — the token itself, short-lived
    and scoped to one document, is the authorization. Only reachable for
    local storage; Supabase's signed URL points at Supabase directly."""
    try:
        document_id = document_service.resolve_download_token(token)
    except InvalidDownloadTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    document = await document_repository.get_by_id(session, document_id)
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")

    if not isinstance(storage_backend, LocalStorageBackend):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Token download only applies to local storage"
        )

    return FileResponse(
        storage_backend.resolve_path(document.storage_path),
        filename=document.filename,
        media_type=document.mime_type,
    )
