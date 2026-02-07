
import asyncio
import asyncpg
from app.core.config import settings

async def reset_alembic():
    db_url = str(settings.DATABASE_URL)
    # Ensure standard postgres URL for asyncpg
    if db_url.startswith("postgresql+asyncpg://"):
        pass
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    conn = await asyncpg.connect(db_url)
    try:
        # Check current version
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        print(f"Current Alembic version in DB: {version}")
        
        # Reset to last known good revision
        target = "af86414342cb"
        await conn.execute("UPDATE alembic_version SET version_num = $1", target)
        print(f"Reset Alembic version in DB to: {target}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(reset_alembic())
