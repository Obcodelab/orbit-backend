from abc import ABC, abstractmethod
from uuid import UUID


class StorageBackend(ABC):
    """Routes/services depend on this interface, never on a concrete
    backend by name — swapping STORAGE_BACKEND is an env var change,
    not a code change."""

    @abstractmethod
    async def save(self, *, file_bytes: bytes, path: str) -> str: ...

    @abstractmethod
    async def read(self, path: str) -> bytes: ...

    @abstractmethod
    async def get_download_url(
        self, *, path: str, project_id: UUID, document_id: UUID
    ) -> str: ...

    @abstractmethod
    async def delete(self, path: str) -> None: ...
