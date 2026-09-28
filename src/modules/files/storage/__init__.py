from core.config import settings
from modules.files.storage.base import StorageBackend
from modules.files.storage.local import LocalStorageBackend, local_storage_backend
from modules.files.storage.supabase import SupabaseStorageBackend

_supabase_storage_backend = SupabaseStorageBackend()


def get_storage_backend() -> StorageBackend:
    if settings.STORAGE_BACKEND == "local":
        return local_storage_backend
    return _supabase_storage_backend


__all__ = [
    "StorageBackend",
    "LocalStorageBackend",
    "SupabaseStorageBackend",
    "get_storage_backend",
]
