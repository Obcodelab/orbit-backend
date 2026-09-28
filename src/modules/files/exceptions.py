class DocumentNotFoundError(Exception):
    """No document exists with this id in this project."""


class FileTooLargeError(Exception):
    """The uploaded file exceeds MAX_FILE_SIZE_MB."""


class UnsupportedFileTypeError(Exception):
    """The uploaded file's MIME type isn't in ALLOWED_FILE_TYPES."""


class NotDocumentUploaderError(Exception):
    """Only the uploader or a project admin/owner can delete a document."""


class InvalidDownloadTokenError(Exception):
    """The download token is missing, expired, or doesn't match this
    document — same collapsed-error treatment as auth tokens, so a
    caller can't distinguish "expired" from "forged"."""
