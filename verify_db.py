"""
Script to verify database tables were created successfully.
"""
import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal


async def verify_tables():
    """Check if all tables were created."""
    async with AsyncSessionLocal() as session:
        # Get list of tables
        result = await session.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """))
        
        tables = [row[0] for row in result.fetchall()]
        
        print("✅ Database Tables Created:")
        print("=" * 50)
        for table in tables:
            print(f"  - {table}")
        
        print("\n" + "=" * 50)
        print(f"Total tables: {len(tables)}")
        
        # Check for ltree extension
        result = await session.execute(text("""
            SELECT extname FROM pg_extension WHERE extname = 'ltree'
        """))
        
        ltree_exists = result.fetchone() is not None
        
        if ltree_exists:
            print("✅ ltree extension is enabled")
        else:
            print("❌ ltree extension is NOT enabled")
        
        return tables, ltree_exists


if __name__ == "__main__":
    asyncio.run(verify_tables())
