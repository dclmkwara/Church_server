
import asyncio
import httpx
from httpx import ASGITransport
import sys
import uuid
import os

# Add authentication login helper usage from test_endpoints.py concept
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User
from sqlalchemy import select

# Configure for test
API_PREFIX = settings.API_V1_PREFIX
BASE_URL = "http://test"

async def verify_hierarchy():
    print("Starting Hierarchy Verification...")
    
    from app.main import app
    transport = ASGITransport(app=app)
    
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
        # 1. Login
        print("\nLogging in...")
        async with AsyncSessionLocal() as db:
            user_query = select(User).limit(1)
            res = await db.execute(user_query)
            user = res.scalars().first()
            if not user:
                print("No user found. Run test_crud.py first.")
                return
            phone = user.phone
            # Reset password to ensure login works
            user.password = hash_password("testpass123")
            db.add(user)
            await db.commit()
            
        login_data = {"username": phone, "password": "testpass123"}
        response = await client.post(f"{API_PREFIX}/auth/login", data=login_data)
        if response.status_code != 200:
             print(f"Login failed: {response.text}")
             return
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Login successful.")

        # IDs for hierarchy
        # Use random suffix to avoid UniqueConstraint errors on re-run
        suffix = str(uuid.uuid4().hex[:4]).upper()
        
        nation_id = f"234-{suffix}"
        state_id = f"KW-{suffix}"
        region_id = f"ILN-{suffix}"
        group_id = f"ILE-{suffix}"
        location_id = f"001-{suffix}"
        fellowship_id = f"F001-{suffix}"

        # 2. Create Nation
        print(f"\nCreating Nation (ID={nation_id})...")
        nation_data = {
            "nation_id": nation_id,
            "continent": "Africa",
            "country_name": "Nigeria",
            "capital": "Abuja",
            "path": f"org.{nation_id}" # Optional, crud logic overrides/sets this usually but we enforce schema validation
        }
        res = await client.post(f"{API_PREFIX}/nations/", json=nation_data, headers=headers)
        if res.status_code == 200:
            data = res.json()
            print(f"   - Success. Path: {data['path']}")
        else:
            print(f"   - Failed: {res.text}")
            return # Cannot proceed

        # 3. Create State
        print(f"\nCreating State (ID={state_id}, Parent={nation_id})...")
        state_data = {
            "state_id": state_id,
            "nation_id": nation_id,
            "state_name": "Kwara",
            "city": "Ilorin"
        }
        res = await client.post(f"{API_PREFIX}/states/", json=state_data, headers=headers)
        if res.status_code == 200:
            data = res.json()
            print(f"   - Success. Path: {data['path']}")
        else:
            print(f"   - Failed: {res.text}")
            return

        # 4. Create Region
        print(f"\nCreating Region (ID={region_id}, Parent={state_id})...")
        region_data = {
            "region_id": region_id,
            "state_id": state_id,
            "region_name": "Ilorin Region",
            "region_head": "Pastor X"
        }
        res = await client.post(f"{API_PREFIX}/regions/", json=region_data, headers=headers)
        if res.status_code == 200:
            data = res.json()
            print(f"   - Success. Path: {data['path']}")
        else:
            print(f"   - Failed: {res.text}")
            return

        # 5. Create Group
        print(f"\nCreating Group (ID={group_id}, Parent={region_id})...")
        group_data = {
            "group_id": group_id,
            "region_id": region_id,
            "group_name": "Ilorin East",
            "group_head": "Pastor Y"
        }
        res = await client.post(f"{API_PREFIX}/groups/", json=group_data, headers=headers)
        if res.status_code == 200:
            data = res.json()
            print(f"   - Success. Path: {data['path']}")
        else:
            print(f"   - Failed: {res.text}")
            return

        # 6. Create Location
        print(f"\nCreating Location (ID={location_id}, Parent={group_id})...")
        location_data = {
            "location_id": location_id,
            "group_id": group_id,
            "location_name": "Amilegbe",
            "church_type": "DLBC",
            "address": "123 Street"
        }
        res = await client.post(f"{API_PREFIX}/locations/", json=location_data, headers=headers)
        if res.status_code == 200:
            data = res.json()
            print(f"   - Success. Path: {data['path']}")
        else:
            print(f"   - Failed: {res.text}")
            return

        # 7. Create Fellowship
        print(f"\nCreating Fellowship (ID={fellowship_id}, Parent={location_id})...")
        fellowship_data = {
            "fellowship_id": fellowship_id,
            "location_id": location_id,
            "fellowship_name": "Peace House",
            "fellowship_address": "456 Avenue"
        }
        res = await client.post(f"{API_PREFIX}/fellowships/", json=fellowship_data, headers=headers)
        if res.status_code == 200:
            data = res.json()
            print(f"   - Success. Path: {data['path']}")
            expected_path = f"org.{nation_id}.{state_id}.{region_id}.{group_id}.{location_id}.{fellowship_id}"
            if data['path'] == expected_path:
                 print("   - Path Verification: PASSED")
            else:
                 print(f"   - Path Verification: FAILED (Expected {expected_path})")
        else:
            print(f"   - Failed: {res.text}")
            return

        # 8. Test Tree View
        print("\nVerifying Tree View...")
        res = await client.get(f"{API_PREFIX}/hierarchy/tree", headers=headers)
        if res.status_code == 200:
            tree = res.json()
            print(f"   - Tree retrieved with {len(tree)} root nodes (nations).")
            # Verify nesting (should find our created nation and its descendants)
            found_nation = False
            for n in tree:
                if n['id'] == nation_id:
                    found_nation = True
                    print(f"   - Found nation {nation_id} in tree.")
                    # Nation -> State
                    if n['children'] and n['children'][0]['id'] == state_id:
                        print(f"   - Found state {state_id} nested correctly.")
                        # State -> Region
                        state = n['children'][0]
                        if state['children'] and state['children'][0]['id'] == region_id:
                             print(f"   - Found region {region_id} nested correctly.")
            
            if found_nation:
                 print("   - Tree Structure: PASSED")
            else:
                 print("   - Tree Structure: FAILED (Nation not found in tree)")
        else:
            print(f"   - Failed to fetch tree: {res.text}")

    print("\nHierarchy Verification Complete!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify_hierarchy())
