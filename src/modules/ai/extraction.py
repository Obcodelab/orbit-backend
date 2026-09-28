from io import BytesIO

from docx import Document as DocxDocument
from pypdf import PdfReader


def extract_text(*, file_bytes: bytes, mime_type: str) -> str:
    if mime_type == "application/pdf":
        reader = PdfReader(BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if mime_type == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ):
        doc = DocxDocument(BytesIO(file_bytes))
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)
    return file_bytes.decode("utf-8", errors="ignore")
