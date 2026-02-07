"""
Test script for Authentication Routes.
"""
import asyncio
import sys
import httpx
from app.core.config import settings
from httpx import ASGITransport

# Base URL
BASE_URL = "http://localhost:8000"
API_PREFIX = settings.API_V1_PREFIX

async def verify_auth():
    print("🚀 Starting Auth Verification...")
    
    from app.main import app
    
    # Use ASGITransport for modern httpx
    transport = ASGITransport(app=app)
    
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        print("\n🔐 Testing Login...")
        
        # 1. Ensure User Exists
        from app.db.session import AsyncSessionLocal
        from app.models.user import User, Worker
        from sqlalchemy import select
        from app.core.security import hash_password
        import uuid
        
        test_phone = "+2349099999999"
        test_pass = "testpass123"
        
        async with AsyncSessionLocal() as db:
            # Check worker
            worker_query = select(Worker).where(Worker.phone == test_phone)
            res = await db.execute(worker_query)
            worker = res.scalars().first()
            
            if not worker:
                print("   - Creating test worker...")
                worker = Worker(
                    worker_id=uuid.uuid4(),
                    user_id="TEST001",
                    location_id="DCM-TEST-LOC",
                    location_name="Test Location",
                    church_type="DLBC",
                    state="Lagos",
                    region="Gbagada",
                    group="Group 1",
                    name="Test User",
                    gender="Male",
                    phone=test_phone,
                    email="testuser@dclm.org",
                    unit="Ushering",
                    status="Active",
                    path="test.path"
                )
                db.add(worker)
                await db.commit()
                await db.refresh(worker)
            
            # Check user
            user_query = select(User).where(User.phone == test_phone)
            res = await db.execute(user_query)
            test_user = res.scalars().first()
            
            if not test_user:
                print("   - Creating test user...")
                test_user = User(
                    worker_id=worker.worker_id,
                    password=hash_password(test_pass),
                    is_active=True,
                    location_id=worker.location_id,
                    name=worker.name,
                    phone=worker.phone,
                    email=worker.email,
                    path=worker.path
                )
                db.add(test_user)
                await db.commit()
            else:
                # Update password explicitly
                test_user.password = hash_password(test_pass)
                db.add(test_user)
                await db.commit()
                
            print("   - Test user ready.")

        # 2. Perform Login Request
        # OAuth2PasswordRequestForm expects form data
        login_data = {
            "username": test_phone,
            "password": test_pass
        }
        
        # OAuth2 form data is sent as x-www-form-urlencoded
        response = await client.post(f"{API_PREFIX}/auth/login", data=login_data)
        
        if response.status_code == 200:
            print("   - ✅ Login Successful!")
            tokens = response.json()
            access_token = tokens["access_token"]
            refresh_token = tokens["refresh_token"]
            print(f"   - Access Token: {access_token[:20]}...")
        else:
            print(f"   - ❌ Login Failed: {response.text}")
            return

        # 3. Test Protected Endpoint (/me)
        print("\n👤 Testing /me endpoint...")
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await client.get(f"{API_PREFIX}/auth/me", headers=headers)
        
        if response.status_code == 200:
            me = response.json()
            print(f"   - ✅ /me Successful! User: {me['name']}")
            print(f"   - Role/Claims check: {me.get('role', 'N/A')}")
        else:
            print(f"   - ❌ /me Failed: {response.text}")

        # 4. Test Refresh Token
        print("\n🔄 Testing /refresh endpoint...")
        response = await client.post(f"{API_PREFIX}/auth/refresh", params={"refresh_token": refresh_token})
        
        if response.status_code == 200:
            print("   - ✅ Refresh Successful!")
            new_tokens = response.json()
            print(f"   - New Access Token: {new_tokens['access_token'][:20]}...")
        else:
            print(f"   - ❌ Refresh Failed: {response.text}")
            
        print("\n✅ Auth Verification Complete!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(verify_auth())
