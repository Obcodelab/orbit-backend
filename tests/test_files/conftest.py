import pytest
import pytest_asyncio
from httpx import AsyncClient

from main import app
from modules.ai.services import ingestion_service
from modules.files.storage import get_storage_backend
from tests.test_files.fake_storage import FakeStorageBackend


@pytest.fixture(autouse=True)
def _skip_real_ingestion(monkeypatch):
    """Uploads schedule a BackgroundTask that calls the real pipeline —
    a real Gemini API call, plus its own DB session against
    DATABASE_URL (background tasks bypass the get_session override, so
    it's never TEST_DATABASE_URL). Never let that actually run here."""

    async def _noop(*, document_id):
        return None

    async def _noop_clone(*, document_id, source_document_id):
        return None

    monkeypatch.setattr(ingestion_service, "ingest_document", _noop)
    monkeypatch.setattr(ingestion_service, "clone_or_ingest", _noop_clone)


@pytest_asyncio.fixture
async def fake_storage_backend(client: AsyncClient) -> FakeStorageBackend:
    backend = FakeStorageBackend()
    app.dependency_overrides[get_storage_backend] = lambda: backend
    yield backend
    app.dependency_overrides.pop(get_storage_backend, None)
