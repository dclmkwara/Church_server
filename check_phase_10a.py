import asyncio
import sys
from datetime import datetime, date

# Add app to path
import os
sys.path.append(os.getcwd())

from app.db.session import AsyncSessionLocal as SessionLocal
from app.crud.crud_fellowship_activities import testimony, prayer_request, attendance_summary, member
from app.models.fellowship_activities import Testimony, PrayerRequest, AttendanceSummary
from app.schemas.fellowship_activities import TestimonyCreate, PrayerRequestCreate, AttendanceSummaryCreate, FellowshipMemberCreate
from app.services.statistics_service import StatisticsService
from app.models.user import User
from sqlalchemy import select

async def check_phase_10a():
    async with SessionLocal() as db:
        print("\n--- Checking Phase 10A: Fellowship & Statistics ---")
        
        # 1. Setup Data - Get a fellowship ID and a user
        # For this test we need an existing fellowship or create one?
        # Let's see if we have any fellowship.
        from app.models.location import Fellowship
        result = await db.execute(select(Fellowship).limit(1))
        fellowship = result.scalars().first()
        
        if not fellowship:
            print("⚠️ No fellowship found in DB. Skipping CRUD tests.")
            return

        print(f"Using Fellowship: {fellowship.name} ({fellowship.fellowship_id})")
        
        # Get a user for 'entered_by'
        result = await db.execute(select(User).limit(1))
        user = result.scalars().first()
        if not user:
            print("⚠️ No user found in DB. Skipping.")
            return
            
        print(f"Using User: {user.email}")
        
        # 2. Test Testimony CRUD
        print("\nTesting Testimony CRUD...")
        t_in = TestimonyCreate(
            fellowship_id=fellowship.fellowship_id,
            date=datetime.now(),
            testifier_name="Brother John",
            content="God has been good!",
            client_id=None
        )
        t_obj = await testimony.create(db, obj_in=t_in, user_id=user.user_id)
        print(f"✅ Created Testimony: {t_obj.id}")
        
        # 3. Test Prayer Request CRUD
        print("\nTesting Prayer Request CRUD...")
        p_in = PrayerRequestCreate(
            fellowship_id=fellowship.fellowship_id,
            date=datetime.now(),
            requestor_name="Sister Jane",
            content="Pray for healing.",
            status="pending"
        )
        p_obj = await prayer_request.create(db, obj_in=p_in, user_id=user.user_id)
        print(f"✅ Created Prayer Request: {p_obj.id}")
        
        # 4. Test Attendance Summary CRUD
        print("\nTesting Attendance Summary CRUD...")
        s_in = AttendanceSummaryCreate(
            fellowship_id=fellowship.fellowship_id,
            month=1,
            year=2026,
            total_meetings=4,
            avg_attendance=15,
            total_offering=5000.00
        )
        s_obj = await attendance_summary.create(db, obj_in=s_in, user_id=user.user_id)
        print(f"✅ Created Attendance Summary: {s_obj.id}")
        
        # 5. Test Statistics Service
        print("\nTesting Statistics Service...")
        scope_path = str(fellowship.path) # Use fellowship path as scope
        
        pop_stats = await StatisticsService.get_population_statistics(db, scope_path=scope_path)
        print(f"✅ Population Stats: {pop_stats}")
        
        church_stats = await StatisticsService.get_church_statistics(db, scope_path=scope_path)
        print(f"✅ Church Stats: {church_stats}")
        
        user_stats = await StatisticsService.get_user_statistics(db, scope_path=scope_path)
        print(f"✅ User Stats: {user_stats}")
        
        print("\n✅ Phase 10A Verification Complete!")

if __name__ == "__main__":
    asyncio.run(check_phase_10a())
