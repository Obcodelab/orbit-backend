from uuid import UUID

from modules.files.storage.base import StorageBackend

_NOT_IMPLEMENTED = (
    "Supabase storage backend isn't implemented yet — set STORAGE_BACKEND=local"
)


class SupabaseStorageBackend(StorageBackend):
    """Stubbed, not implemented — needs the supabase-py client and real
    project credentials to build and test against. Fails loudly if
    selected rather than silently behaving like local storage."""

    async def save(self, *, file_bytes: bytes, path: str) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    async def read(self, path: str) -> bytes:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    async def get_download_url(
        self, *, path: str, project_id: UUID, document_id: UUID
    ) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED)

    async def delete(self, path: str) -> None:
        raise NotImplementedError(_NOT_IMPLEMENTED)
