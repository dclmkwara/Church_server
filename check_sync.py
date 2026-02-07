
import asyncio
import uuid
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal
from app.models.audit import IdempotencyKey, AuditLog

async def check_sync_tables():
    async with AsyncSessionLocal() as db:
        print("Checking tables...")
        try:
            # Check IdempotencyKey table
            result = await db.execute(text("SELECT count(*) FROM idempotency_keys"))
            count = result.scalar()
            print(f"IdempotencyKey table exists. Row count: {count}")
            
            # Check AuditLog table
            result = await db.execute(text("SELECT count(*) FROM audit_logs"))
            count = result.scalar()
            print(f"AuditLog table exists. Row count: {count}")
            
            # Create a dummy idempotency key
            client_id = uuid.uuid4()
            resource_id = uuid.uuid4()
            
            key = IdempotencyKey(
                client_id=client_id,
                resource_type="test",
                resource_id=resource_id
            )
            db.add(key)
            await db.commit()
            print(f"Successfully inserted test IdempotencyKey: {client_id}")
            
            # Verify retrieval
            stmt = select(IdempotencyKey).where(IdempotencyKey.client_id == client_id)
            result = await db.execute(stmt)
            retrieved = result.scalar_one_or_none()
            
            if retrieved:
                print(f"Successfully retrieved key: {retrieved}")
            else:
                print("Failed to retrieve key!")
                
        except Exception as e:
            print(f"Error checking tables: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_sync_tables())
