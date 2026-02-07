"""
Test script for User and Worker endpoints.
"""
import asyncio
import sys
import httpx
from httpx import ASGITransport
from app.core.config import settings
from app.core.security import hash_password
import uuid

# Base URL
API_PREFIX = settings.API_V1_PREFIX

async def verify_endpoints():
    print("Starting API Verification...")
    
    from app.main import app
    from app.db.session import AsyncSessionLocal
    from app.models.user import User, Worker
    from sqlalchemy import select
    
    transport = ASGITransport(app=app)
    
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login to get token
        print("\nLogging in...")
        
        # Ensure we have a user
        async with AsyncSessionLocal() as db:
            user_query = select(User).limit(1)
            res = await db.execute(user_query)
            user = res.scalars().first()
            if not user:
                print("No user found. Run test_crud.py first.")
                return
            
            # Reset password to known one
            user.password = hash_password("testpass123")
            db.add(user)
            await db.commit()
            phone = user.phone
            
        login_data = {"username": phone, "password": "testpass123"}
        response = await client.post(f"{API_PREFIX}/auth/login", data=login_data)
        
        if response.status_code != 200:
             print(f"Login failed: {response.text}")
             return
             
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Login successful.")
        
        # 2. Test GET /workers
        print("\nTesting GET /workers...")
        response = await client.get(f"{API_PREFIX}/workers/", headers=headers)
        if response.status_code == 200:
            workers = response.json()
            print(f"   - Found {len(workers)} workers.")
        else:
            print(f"   - Failed: {response.text}")
            
        # 3. Test POST /workers
        print("\nTesting POST /workers...")
        new_worker_phone = f"+23480{uuid.uuid4().int % 100000000:08d}"
        worker_data = {
            "location_id": "DCM-TEST-NEW",
            "location_name": "New Test Loc",
            "church_type": "DLBC",
            "state": "Lagos",
            "region": "Region X",
            "group": "Group Y",
            "name": "New Worker",
            "gender": "Male",
            "phone": new_worker_phone,
            "email": f"worker{uuid.uuid4().hex[:6]}@test.com",
            "unit": "Choir",
            "status": "Active"
        }
        
        response = await client.post(f"{API_PREFIX}/workers/", json=worker_data, headers=headers)
        if response.status_code == 200:
            new_worker = response.json()
            print(f"   - Created worker: {new_worker['name']} ({new_worker['worker_id']})")
            worker_id = new_worker['worker_id']
        else:
            print(f"   - Failed: {response.text}")
            return
            
        # 4. Test GET /users
        print("\nTesting GET /users...")
        response = await client.get(f"{API_PREFIX}/users/", headers=headers)
        if response.status_code == 200:
            users = response.json()
            print(f"   - Found {len(users)} users.")
        else:
            print(f"   - Failed: {response.text}")

        # 5. Test POST /users (Create user for new worker)
        print("\nTesting POST /users...")
        user_data = {
            "email": worker_data["email"],
            "is_active": True,
            "worker_id": worker_id,
            "password": "newuserpass123",
            "roles": [] # Optional
        }
        
        response = await client.post(f"{API_PREFIX}/users/", json=user_data, headers=headers)
        if response.status_code == 200:
            new_user = response.json()
            print(f"   - Created user: {new_user['name']}")
            new_user_id = new_user['user_id']
        else:
            print(f"   - Failed: {response.text}")
            return

        # 6. Test Assign Role
        print("\nTesting POST /users/{id}/assign-role...")
        # Check available roles
        async with AsyncSessionLocal() as db:
             # Just pick a random role ID to try
             from app.models.user import Role
             res = await db.execute(select(Role).limit(1))
             role = res.scalars().first()
             role_id = role.id if role else 1
             
        role_data = [role_id]
        response = await client.post(
            f"{API_PREFIX}/users/{new_user_id}/assign-role", 
            json=role_data, 
            headers=headers
        )
        
        if response.status_code == 200:
             print("   - Role assigned successfully.")
             updated_user = response.json()
             try:
                 print(f"   - Roles: {[r['role_name'] for r in updated_user['roles']]}")
             except:
                 print(f"   - Roles: {updated_user.get('roles')}")
        else:
             print(f"   - Assign Role Failed (Expected if low privileges): {response.text}")
             
        print("\nAPI Verification Complete!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(verify_endpoints())
