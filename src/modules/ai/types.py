from enum import StrEnum
from typing import TypedDict


class AIMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class CitationDict(TypedDict):
    """Shape of one entry in AIMessage.citations — ids are str, not UUID,
    since this is what's actually stored in the JSON column after
    Citation.model_dump(mode="json") serializes them."""

    document_id: str
    chunk_id: str
    snippet: str
