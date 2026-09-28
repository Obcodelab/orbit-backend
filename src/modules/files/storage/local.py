import asyncio
from pathlib import Path
from uuid import UUID

from core.config import PROJECT_ROOT, settings
from core.security import create_download_token
from modules.files.storage.base import StorageBackend


class LocalStorageBackend(StorageBackend):
    """No CDN/object-store sits in front of a local disk, so there's no
    real signed URL to issue. get_download_url instead returns a
    short-lived token embedded in our own download route, which
    validates it and streams the file."""

    def __init__(self) -> None:
        upload_dir = Path(settings.UPLOAD_DIR)
        self._root = (
            upload_dir if upload_dir.is_absolute() else PROJECT_ROOT / upload_dir
        )
        self._root.mkdir(parents=True, exist_ok=True)

    async def save(self, *, file_bytes: bytes, path: str) -> str:
        full_path = self._root / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(full_path.write_bytes, file_bytes)
        return path

    async def read(self, path: str) -> bytes:
        return await asyncio.to_thread(self._root.joinpath(path).read_bytes)

    async def get_download_url(
        self, *, path: str, project_id: UUID, document_id: UUID
    ) -> str:
        token, _ = create_download_token({"document_id": str(document_id)})
        return f"/api/v1/files/download?token={token}"

    async def delete(self, path: str) -> None:
        await asyncio.to_thread(self._root.joinpath(path).unlink, True)

    def resolve_path(self, path: str) -> Path:
        return self._root / path


local_storage_backend = LocalStorageBackend()
