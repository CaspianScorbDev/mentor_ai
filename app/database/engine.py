from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import cfg

db = cfg.database

engine = create_async_engine(
    url=db.database_dsn,
    echo=db.echo,
    pool_size=db.pool_size,
    max_overflow=db.max_overflow,
    pool_timeout=db.pool_timeout,
    pool_recycle=db.pool_recycle,
    pool_pre_ping=db.pre_ping,
    connect_args=db.connect_args,
)

Session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with Session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
