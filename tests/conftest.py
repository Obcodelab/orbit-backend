import itertools
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import core.all_models  # noqa: F401 — populates Base.metadata before create_all
from core.config import settings
from core.database import Base, get_session
from core.rate_limit import limiter
from main import app
from modules.auth.models import User, UserVerificationCode
from modules.auth.types import VerificationPurpose


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """slowapi's limiter is a process-global singleton with in-memory
    storage — without resetting it, tests would share rate-limit counters
    across every other test in the run, not just within themselves."""
    limiter.reset()


if not settings.TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL must be set to run tests — see .env.example")

test_engine = create_async_engine(settings.TEST_DATABASE_URL)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _test_schema() -> AsyncGenerator[None]:
    """Rebuilds the schema from the current models once per test run —
    Base.metadata.create_all(), not real Alembic migrations. Fast and
    always matches the models exactly; it doesn't exercise the migration
    files themselves, which get checked by hand when they're generated."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """One session per test, never committed — only the real get_session()
    (overridden below for the duration of each test) ever commits, so
    rolling back here is enough to undo everything the test did."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def _override_get_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# --- shared auth helpers, for this module's tests and every future one ------


async def _get_code(
    db_session: AsyncSession, email: str, purpose: VerificationPurpose
) -> str:
    user = (
        await db_session.execute(select(User).where(User.email == email))
    ).scalar_one()
    code_row = (
        await db_session.execute(
            select(UserVerificationCode).where(
                UserVerificationCode.user_id == user.id,
                UserVerificationCode.purpose == purpose,
            )
        )
    ).scalar_one()
    return code_row.code


async def _get_verification_code(db_session: AsyncSession, email: str) -> str:
    return await _get_code(db_session, email, VerificationPurpose.EMAIL_VERIFICATION)


async def _get_reset_code(db_session: AsyncSession, email: str) -> str:
    return await _get_code(db_session, email, VerificationPurpose.PASSWORD_RESET)


async def _register_and_verify(
    client: AsyncClient, db_session: AsyncSession, register_payload: dict
) -> dict:
    """Registers + verifies an account, returning the token pair body."""
    await client.post("/api/v1/auth/register", json=register_payload)
    code = await _get_verification_code(db_session, register_payload["email"])
    verify = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": register_payload["email"], "code": code},
    )
    return verify.json()


# Fixture wrappers around the plain helpers above — a bare `from conftest
# import helper` gets fragile once test files are nested a few directories
# deep, while fixtures resolve correctly regardless of nesting depth.


@pytest_asyncio.fixture
def get_verification_code(
    db_session: AsyncSession,
) -> Callable[[str], Awaitable[str]]:
    async def _get(email: str) -> str:
        return await _get_verification_code(db_session, email)

    return _get


@pytest_asyncio.fixture
def get_reset_code(db_session: AsyncSession) -> Callable[[str], Awaitable[str]]:
    async def _get(email: str) -> str:
        return await _get_reset_code(db_session, email)

    return _get


@pytest_asyncio.fixture
def register_and_verify(
    client: AsyncClient, db_session: AsyncSession
) -> Callable[[dict], Awaitable[dict]]:
    async def _do(register_payload: dict) -> dict:
        return await _register_and_verify(client, db_session, register_payload)

    return _do


@dataclass
class AuthedUser:
    user: User
    access_token: str
    refresh_token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}


@pytest_asyncio.fixture
def create_authenticated_user(
    client: AsyncClient, db_session: AsyncSession
) -> Callable[..., Awaitable[AuthedUser]]:
    """Factory for a real, verified, logged-in user — doesn't require
    knowing auth's registration payload shape. Call more than once (with
    distinct emails) for several independent users, e.g. RBAC tests."""
    counter = itertools.count(1)

    async def _create(
        *,
        email: str | None = None,
        password: str = "Password1!",
        first_name: str = "Test",
        last_name: str = "User",
    ) -> AuthedUser:
        if email is None:
            email = f"user{next(counter)}@example.com"

        await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "confirm_password": password,
                "first_name": first_name,
                "last_name": last_name,
            },
        )
        code = await _get_verification_code(db_session, email)
        verify = await client.post(
            "/api/v1/auth/verify-email", json={"email": email, "code": code}
        )
        body = verify.json()

        user = (
            await db_session.execute(select(User).where(User.email == email))
        ).scalar_one()

        return AuthedUser(
            user=user,
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
        )

    return _create


@pytest_asyncio.fixture
async def authenticated_user(
    create_authenticated_user: Callable[..., Awaitable[AuthedUser]],
) -> AuthedUser:
    """The common case — one already-verified, logged-in user with default
    details. Use create_authenticated_user directly when a test needs more
    than one user or specific details."""
    return await create_authenticated_user()
