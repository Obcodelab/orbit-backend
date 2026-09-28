from typing import Annotated

from fastapi import Depends

from modules.files.storage import StorageBackend, get_storage_backend

StorageBackendDep = Annotated[StorageBackend, Depends(get_storage_backend)]
