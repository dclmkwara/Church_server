"""
Database reset utility.

WARNING: This script will DROP ALL TABLES in the database.
Use this only when you want to start fresh during development.
"""
import asyncio
import os
import sys
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from app.db.session import create_async_engine
from app.core.config import settings


async def reset_database():
    """Drop all tables and reset the database."""
    print("⚠️  WARNING: This will DROP ALL TABLES in the 'dclm_db' database!")
    print("Are you sure? (y/n)")
    
    # Simple check for interactive mode, otherwise force 'y' if argument provided
    if len(sys.argv) > 1 and sys.argv[1] == "--force":
        confirm = "y"
    else:
        confirm = input("> ")
    
    if confirm.lower() != "y":
        print("❌ Aborted.")
        return

    print("\nConnecting to database...")
    engine = create_async_engine(
        str(settings.DATABASE_URL),
        echo=False,
        poolclass=NullPool,
    )
    
    async with engine.begin() as conn:
        print("🗑️  Dropping all tables...")
        # Disable triggers to avoid dependency issues during drop
        await conn.execute(text("SET session_replication_role = 'replica';"))
        
        # Get all table names
        result = await conn.execute(text("""
            SELECT tablename FROM pg_tables WHERE schemaname = 'public'
        """))
        tables = [row[0] for row in result.fetchall()]
        
        if not tables:
            print("   No tables found.")
        else:
            for table in tables:
                print(f"   - Dropping {table}")
                await conn.execute(text(f"DROP TABLE IF EXISTS \"{table}\" CASCADE"))
        
        # Re-enable triggers
        await conn.execute(text("SET session_replication_role = 'origin';"))
        
    await engine.dispose()
    print("\n✅ Database reset complete.")
    print("\n🚀 running alembic upgrade head...")
    
    # Run alembic upgrade
    ret = os.system("alembic upgrade head")
    if ret == 0:
        print("\n✅ Migration applied successfully!")
    else:
        print("\n❌ Migration failed.")


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(reset_database())
