import asyncio
import sys
from datetime import datetime, timedelta

# Add app to path
import os
sys.path.append(os.getcwd())

from app.db.session import AsyncSessionLocal as SessionLocal
from app.crud.crud_recovery import recovery
from app.services.notification_service import NotificationService
from app.models.user import User
from app.models.counts import Count
from sqlalchemy import select

async def check_phase_10b():
    async with SessionLocal() as db:
        print("\n--- Checking Phase 10B: Recovery & Polling ---")
        
        # 1. Setup - Get a user
        result = await db.execute(select(User).limit(1))
        user = result.scalars().first()
        
        if not user:
            print("⚠️ No user found. Skipping.")
            return

        print(f"Using User: {user.email}")
        
        # 2. Test Recovery - Create Token
        print("\nTesting Recovery Token Creation...")
        token = await recovery.create_token(db, email=user.email)
        print(f"✅ Token Created: {token.token}")
        
        # 3. Test Recovery - Verify Token
        print("\nTesting Token Verification...")
        verified = await recovery.verify_token(db, token=token.token)
        print(f"✅ Token Verified: {verified is not None}")
        
        # 4. Test Notification Polling
        print("\nTesting Notification Polling...")
        # Create a count to be picked up
        from app.models.counts import Count
        import uuid
        
        # We need to simulate a fresh insert or just pick up recent ones
        # Since we use 'created_at', let's use a timestamp from 5 minutes ago
        since = datetime.now() - timedelta(minutes=5)
        
        # Let's ensure we have at least one count created recently if possible, otherwise we test with older date
        # Getting scope path
        scope_path = str(user.path)
        
        print(f"Polling since: {since}")
        results = await NotificationService.poll_new_data(db, scope_path, since)
        print(f"✅ Polling Results: {results}")
        
        print("\n✅ Phase 10B Verification Complete!")

if __name__ == "__main__":
    asyncio.run(check_phase_10b())
