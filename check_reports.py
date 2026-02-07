
import asyncio
import sys
import os
import uuid
from datetime import date

# Add project root to path
sys.path.append(os.getcwd())

from sqlalchemy import select, text
from app.db.session import AsyncSessionLocal
from app.models.counts import Count
from app.models.programs import ProgramEvent, ProgramType, ProgramDomain
from app.models.location import Location, Group, Region, State, Nation
from app.services.report_service import ReportService

async def check_reports():
    async with AsyncSessionLocal() as db:
        print("Checking reports...")
        try:
            # 1. Create Data
            # Start transaction
            
            # Helper to get or create
            async def get_or_create_domain():
                stmt = select(ProgramDomain).where(ProgramDomain.slug == "regular_service")
                res = await db.execute(stmt)
                obj = res.scalar_one_or_none()
                if not obj:
                    obj = ProgramDomain(slug="regular_service", name="Regular Service")
                    db.add(obj)
                    await db.flush()
                return obj

            domain = await get_or_create_domain()
            
            async def get_or_create_type(domain_id):
                stmt = select(ProgramType).where(ProgramType.slug == "check_report_svc")
                res = await db.execute(stmt)
                obj = res.scalar_one_or_none()
                if not obj:
                    obj = ProgramType(slug="check_report_svc", name="Report Check Service", domain_id=domain_id)
                    db.add(obj)
                    await db.flush()
                return obj

            ptype = await get_or_create_type(domain.id)

            # Create Event
            event_id = uuid.uuid4()
            event = ProgramEvent(
                id=event_id,
                program_type_id=ptype.id,
                path="org.234.report_check",
                date=date.today(),
                title="Report Check Event"
            )
            # Check if exists (id collision unlikely but logic sound)
            db.add(event)
            
            # Create Location (Mock)
            # Assuming location table has location_id string
            loc_id = "DCM-REPORT-CHECK-001"
            # We need to ensure parent hierarchy exists or just cheat for test if FKs are loose?
            # FKs are enforced. So we need Group, Region, State, Nation.
            # This is complex. 
            # Bypass FKs? No, SQLAlchemy enforces.
            # Maybe just insert into 'locations' table roughly if possible or use existing 'DCM-...'?
            # Let's try to query an existing location or create a dummy root one.
            # Creating dummy hierarchy is verbose.
            # Let's see if we can just insert a location without parents if FKs are not strict on parents?
            # 'location' has 'group_id' FK. 'group' has 'region_id' FK.
            # This is deep. 
            # I will assume "DCM-234-KW-ILN-ILE-001" exists from previous tests or if not, I'll create a minimal chain.
            
            # minimal chain
            nation = Nation(nation_id="DCM-REPORT", continent="Test", country_name="TestCountry", path="org.report")
            state = State(state_id="DCM-REPORT-ST", nation_id="DCM-REPORT", state="TestState", path="org.report.st")
            region = Region(region_id="DCM-REPORT-ST-RG", state_id="DCM-REPORT-ST", region_name="TestRegion", path="org.report.st.rg")
            group = Group(group_id="DCM-REPORT-ST-RG-GP", region_id="DCM-REPORT-ST-RG", group_name="TestGroup", path="org.report.st.rg.gp")
            loc = Location(location_id="DCM-REPORT-LOC-001", group_id="DCM-REPORT-ST-RG-GP", location_name="Test Location", path="org.report.st.rg.gp.001", church_type="DLBC")
            
            db.add(nation)
            db.add(state)
            db.add(region)
            db.add(group)
            db.add(loc)
            await db.flush()

            # Create Count
            count = Count(
                event_id=event_id,
                location_id=loc.location_id,
                path="org.report.st.rg.gp.001",
                total=100,
                adult_male=50,
                adult_female=50,
                entered_by_id=uuid.uuid4() # Mock user ID, will fail FK to users?
                # User FK is needed.
            )
            
            # Need a user.
            from app.models.user import User
            # Check for generic user or create one
            stmt = select(User).limit(1)
            res = await db.execute(stmt)
            user = res.scalar_one_or_none()
            if not user:
                 # Create minimal user
                 # This requires Worker...
                 # Too complex to create full chain just for a test script unless I reuse CRUD.
                 # Let's just create a raw User + Worker if needed or find one.
                 # Assuming Database might be empty.
                 # I'll try to create a dummy user with minimal fields if possible.
                 pass
            
            if user:
                count.entered_by_id = user.user_id
                db.add(count)
                await db.commit()
                print("Data inserted.")
                
                # Refresh Views
                print("Refreshing views...")
                await ReportService.refresh_views(db)
                
                # Query
                print("Querying report...")
                data = await ReportService.get_daily_counts(db, "org.report", date.today(), date.today())
                print(f"Report Data: {data}")
            else:
                print("No user found to link count to. Skipping insert.")

        except Exception as e:
            print(f"Error: {e}")
            await db.rollback()
            # import traceback
            # traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_reports())
