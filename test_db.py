"""
Test database connection.
"""
import asyncio
from app.db.session import test_connection


async def main():
    print("Testing database connection...")
    result = await test_connection()
    if result:
        print("✅ Database connection SUCCESS")
    else:
        print("❌ Database connection FAILED")
        print("Please check your .env file and ensure:")
        print("1. DATABASE_URL is correct")
        print("2. PostgreSQL is running")
        print("3. ltree extension is enabled: CREATE EXTENSION IF NOT EXISTS ltree;")


if __name__ == "__main__":
    asyncio.run(main())
