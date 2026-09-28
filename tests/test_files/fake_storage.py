from uuid import UUID

from modules.files.storage.base import StorageBackend


class FakeStorageBackend(StorageBackend):
    """In-memory test double — the real point of StorageBackend being an
    interface is that tests can swap it out cleanly, same as any other
    injected dependency, without touching real disk."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def save(self, *, file_bytes: bytes, path: str) -> str:
        self.files[path] = file_bytes
        return path

    async def read(self, path: str) -> bytes:
        return self.files[path]

    async def get_download_url(
        self, *, path: str, project_id: UUID, document_id: UUID
    ) -> str:
        return f"https://fake-storage.test/{path}"

    async def delete(self, path: str) -> None:
        self.deleted.append(path)
        self.files.pop(path, None)
