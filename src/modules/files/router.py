from fastapi import APIRouter

from .apis.document import document_router
from .apis.download import download_router

files_router = APIRouter()
files_router.include_router(document_router)
files_router.include_router(download_router)
