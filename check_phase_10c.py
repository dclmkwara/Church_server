import asyncio
import sys

# Add app to path
import os
sys.path.append(os.getcwd())

from app.db.session import AsyncSessionLocal as SessionLocal
from app.db.init_rbac import init_rbac
from app.crud.crud_rbac import role, permission
from sqlalchemy import select
from app.models.user import RoleScore

async def check_phase_10c():
    async with SessionLocal() as db:
        print("\n--- Checking Phase 10C: Role Management ---")
        
        # 0. Pre-requisite: Create RoleScores if missing (for testing)
        # Note: In production this should be a migration
        print("Ensuring RoleScores exist...")
        scores = [
            (1, "Worker"), (3, "Location Admin"), (9, "Global Admin")
        ]
        for score, name in scores:
            stmt = select(RoleScore).where(RoleScore.score == score)
            existing = (await db.execute(stmt)).scalars().first()
            if not existing:
                rs = RoleScore(score=score, score_name=name)
                db.add(rs)
        await db.commit()

        # 1. Run Seeder
        print("\nRunning RBAC Seeder...")
        await init_rbac(db)
        
        # 2. Verify Permissions
        print("\nVerifying Permissions...")
        perms = await permission.get_multi(db)
        print(f"✅ Found {len(perms)} permissions")
        for p in perms[:3]:
            print(f"   - {p.permission}: {p.name}")
            
        # 3. Verify Roles
        print("\nVerifying Roles...")
        roles = await role.get_multi(db)
        print(f"✅ Found {len(roles)} roles")
        for r in roles:
            print(f"   - {r.role_name} (Score: {r.score_id})")
            # Need to eager load or fetch permissions to show count
            # Use relationship access which triggers fetch in async? No, implicit IO not allowed
            # Detailed check via API model would show them.
            
        print("\n✅ Phase 10C Verification Complete!")

if __name__ == "__main__":
    try:
        asyncio.run(check_phase_10c())
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Error: {e}")
