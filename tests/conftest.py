from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

import main
from app.core.config import cfg
from app.database.engine import get_session
from app.integrations.base import StreamChunk
from app.services.llm import ChatTurn, Persona, get_llm_service


class FakeLLM:
    """Deterministic stand-in that never touches the network."""

    async def stream(
        self, persona: Persona, turns: list[ChatTurn]
    ) -> AsyncIterator[StreamChunk]:
        for token in ("Hel", "lo", "!"):
            yield StreamChunk("content", token)

    async def close(self) -> None:
        return None


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(
        cfg.database.database_dsn,
        poolclass=NullPool,
        connect_args=cfg.database.connect_args,
    )
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - any failure means the DB is not usable
        await engine.dispose()
        pytest.skip(f"database is not available: {exc}")

    yield engine
    await engine.dispose()


def _maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture
async def session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with _maker(db_engine)() as db_session:
        yield db_session


@pytest_asyncio.fixture
async def client(db_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    maker = _maker(db_engine)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with maker() as db_session:
            yield db_session

    main.app.dependency_overrides[get_session] = override_session
    main.app.dependency_overrides[get_llm_service] = lambda: FakeLLM()

    transport = ASGITransport(app=main.app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as http_client:
        yield http_client

    main.app.dependency_overrides.clear()
