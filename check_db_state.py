"""
Quick script to check database state after failed migration
"""
import asyncio
from sqlalchemy import text
from app.db.session import async_session

async def check_tables():
    async with async_session() as db:
        # Check what tables exist
        result = await db.execute(text("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename LIKE '%count%' OR tablename LIKE '%offering%' OR tablename LIKE '%fellowship_attendance%'
            ORDER BY tablename
        """))
        tables = result.fetchall()
        print("\\n=== Tables matching counts/offerings/fellowship_attendance ===")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Check if date column exists in counts
        result = await db.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'counts' 
            ORDER BY ordinal_position
        """))
        cols = result.fetchall()
        print("\\n=== Counts table columns ===")
        for col in cols:
            print(f"  - {col[0]}: {col[1]}")
        
        # Check if date column exists in offerings
        result = await db.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'offerings' 
            ORDER BY ordinal_position
        """))
        cols = result.fetchall()
        print("\\n=== Offerings table columns ===")
        for col in cols:
            print(f"  - {col[0]}: {col[1]}")

if __name__ == "__main__":
    asyncio.run(check_tables())
