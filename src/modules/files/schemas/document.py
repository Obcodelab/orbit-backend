from datetime import datetime

from pydantic import UUID7, BaseModel, Field

from core.schemas import FROM_ORM


class DocumentResponse(BaseModel):
    model_config = FROM_ORM

    document_id: UUID7 = Field(validation_alias="id")
    task_id: UUID7 | None
    uploader_id: UUID7
    filename: str
    file_size: int
    mime_type: str
    created_at: datetime


class DownloadUrlResponse(BaseModel):
    url: str
