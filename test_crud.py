"""
Script to verify CRUD operations.
"""
import asyncio
import random
from app.db.session import AsyncSessionLocal
from app.schemas.user import WorkerCreate, UserCreate, RoleCreate
from app.crud import worker, user, role
from app.models.user import RoleScore


async def verify_crud():
    print("Starting CRUD Verification...")
    
    async with AsyncSessionLocal() as db:
        # 1. Create Role Scores (Seeds) if they don't exist
        print("\nSeeding Role Scores...")
        scores = [
            (1, "Worker", "General Worker"),
            (3, "LocationPastor", "Location Pastor"),
            (4, "GroupPastor", "Group Pastor"),
        ]
        
        for s_val, s_name, s_desc in scores:
            existing = await role.get_score_by_value(db, score=s_val)
            if not existing:
                rs = RoleScore(score=s_val, score_name=s_name, description=s_desc)
                db.add(rs)
                print(f"   - Created RoleScore: {s_name} ({s_val})")
            else:
                print(f"   - RoleScore exists: {s_name} ({s_val})")
        await db.commit()
        
        # 2. Create a Role
        print("\nCreating Role...")
        location_pastor_score = await role.get_score_by_value(db, score=3)
        role_name = "Location Pastor"
        existing_role = await role.get_by_name(db, name=role_name)
        
        if not existing_role:
            r_in = RoleCreate(
                role_name=role_name, 
                description="Oversees a location",
                score_id=location_pastor_score.id
            )
            r = await role.create_with_score(db, obj_in=r_in)
            print(f"   - Created Role: {r.role_name}")
            role_id = r.id
        else:
            print(f"   - Role exists: {existing_role.role_name}")
            role_id = existing_role.id

        # 3. Create a Worker
        print("\nCreating Worker...")
        import time
        ts = int(time.time())
        suffix = str(ts)[-4:]
        phone = f"+234901234{suffix}"  # Last 4 digits vary
        email = f"worker{ts}@dclm.org"
        location_id = "DCM-234-KW-ILN-ILE-001"
        
        w_in = WorkerCreate(
            location_id=location_id,
            location_name="Ilorin East Location",
            church_type="DLBC",
            state="Kwara",
            region="Ilorin",
            group="Ilorin East",
            name="John Doe",
            gender="Male",
            phone=phone,
            email=email,
            unit="Pastoral",
            status="Active"
        )
        
        new_worker = await worker.create(db, obj_in=w_in)
        print(f"   - Created Worker: {new_worker.name} ({new_worker.worker_id})")
        print(f"   - Auto-generated Path: {new_worker.path}")
        print(f"   - Verify Path Format: {'org.234.kw.iln.ile.001' in str(new_worker.path)}")

        # 4. Create User linked to Worker
        print("\nCreating User...")
        u_in = UserCreate(
            email=email,
            worker_id=new_worker.worker_id,
            password="securepassword123",
            roles=[role_id]
        )
        
        new_user = await user.create(db, obj_in=u_in)
        print(f"   - Created User: {new_user.name} ({new_user.user_id})")
        print(f"   - Denormalized Phone: {new_user.phone}")
        print(f"   - Hashed Password: {new_user.password[:10]}...")
        
        # 5. Verify Authentication
        print("\nVerifying Authentication...")
        auth_user = await user.authenticate(db, phone=phone, password="securepassword123")
        if auth_user:
            print(f"   - Authentication Successful for {auth_user.name}")
        else:
            print(f"   - Authentication FAILED")
            
        # 6. Verify Scope Filtering
        print("\nVerifying Scope Filtering...")
        scope = "org.234.kw.iln"  # Region level
        workers_in_scope = await worker.get_multi_by_scope(db, scope_path=scope)
        print(f"   - found {len(workers_in_scope)} workers in scope '{scope}'")
        
        scope_narrow = "org.234.kw.iln.ile.001" # Exact location
        workers_narrow = await worker.get_multi_by_scope(db, scope_path=scope_narrow)
        print(f"   - found {len(workers_narrow)} workers in scope '{scope_narrow}'")
        
        scope_other = "org.234.lg" # Lagos state (should be empty/different)
        workers_other = await worker.get_multi_by_scope(db, scope_path=scope_other)
        print(f"   - found {len(workers_other)} workers in scope '{scope_other}'")

        print("\nCRUD Verification Complete!")


if __name__ == "__main__":
    asyncio.run(verify_crud())
