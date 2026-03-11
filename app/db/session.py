"""
Database session management with async SQLAlchemy.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from typing import AsyncGenerator
from app.core.config import settings


# Normalize DATABASE_URL for asyncpg compatibility
# Render/Supabase may provide postgresql:// but asyncpg needs postgresql+asyncpg://
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)


# Create async engine
engine = create_async_engine(
    _db_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database session.
    
    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def inject_scope(session: AsyncSession, scope_path: str) -> None:
    """
    Inject scope path into session for Row-Level Security.
    
    Args:
        session: Database session
        scope_path: ltree path for scope filtering (e.g., 'org.234.kw.iln.ile')
    """
    await session.execute(
        text("SELECT set_config('app.scope_path', :path, true)"),
        {"path": scope_path}
    )


async def test_connection() -> bool:
    """
    Test database connection.
    
    Returns:
        bool: True if connection successful
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
