from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.core.security import hash_password
from app.crud.crud_location import group as crud_group
from app.crud.crud_location import location as crud_location
from app.crud.crud_location import nation as crud_nation
from app.crud.crud_location import region as crud_region
from app.crud.crud_location import state as crud_state
from app.db.init_rbac import init_rbac
from app.db.session import AsyncSessionLocal, engine
from app.models.core import generate_display_id, generate_public_person_code
from app.models.location import Group, Location, Nation, Region, State
from app.models.programs import ProgramDomain, ProgramType
from app.models.user import Role, User, Worker
from app.schemas.location import GroupCreate, LocationCreate, NationCreate, RegionCreate, StateCreate

WEST_AFRICA_DIVISION = "West Africa Division"

WEST_AFRICA_NATIONS = [
    {"nation_id": "229", "country_name": "Benin", "capital": "Porto-Novo"},
    {"nation_id": "226", "country_name": "Burkina Faso", "capital": "Ouagadougou"},
    {"nation_id": "238", "country_name": "Cabo Verde", "capital": "Praia"},
    {"nation_id": "225", "country_name": "Cote d'Ivoire", "capital": "Yamoussoukro"},
    {"nation_id": "220", "country_name": "The Gambia", "capital": "Banjul"},
    {"nation_id": "233", "country_name": "Ghana", "capital": "Accra"},
    {"nation_id": "224", "country_name": "Guinea", "capital": "Conakry"},
    {"nation_id": "245", "country_name": "Guinea-Bissau", "capital": "Bissau"},
    {"nation_id": "231", "country_name": "Liberia", "capital": "Monrovia"},
    {"nation_id": "223", "country_name": "Mali", "capital": "Bamako"},
    {"nation_id": "227", "country_name": "Niger", "capital": "Niamey"},
    {"nation_id": "234", "country_name": "Nigeria", "capital": "Abuja"},
    {"nation_id": "221", "country_name": "Senegal", "capital": "Dakar"},
    {"nation_id": "232", "country_name": "Sierra Leone", "capital": "Freetown"},
    {"nation_id": "228", "country_name": "Togo", "capital": "Lome"},
]

NIGERIA_STATES = [
    ("AB", "Abia State"),
    ("AD", "Adamawa State"),
    ("AK", "Akwa Ibom State"),
    ("AN", "Anambra State"),
    ("BA", "Bauchi State"),
    ("BY", "Bayelsa State"),
    ("BN", "Benue State"),
    ("BO", "Borno State"),
    ("CR", "Cross River State"),
    ("DT", "Delta State"),
    ("EB", "Ebonyi State"),
    ("ED", "Edo State"),
    ("EK", "Ekiti State"),
    ("EN", "Enugu State"),
    ("FC", "Federal Capital Territory"),
    ("GM", "Gombe State"),
    ("IM", "Imo State"),
    ("JG", "Jigawa State"),
    ("KD", "Kaduna State"),
    ("KN", "Kano State"),
    ("KT", "Katsina State"),
    ("KB", "Kebbi State"),
    ("KG", "Kogi State"),
    ("KW", "Kwara State"),
    ("LG", "Lagos State"),
    ("NS", "Nasarawa State"),
    ("NG", "Niger State"),
    ("OG", "Ogun State"),
    ("ON", "Ondo State"),
    ("OS", "Osun State"),
    ("OY", "Oyo State"),
    ("PL", "Plateau State"),
    ("RV", "Rivers State"),
    ("SK", "Sokoto State"),
    ("TR", "Taraba State"),
    ("YB", "Yobe State"),
    ("ZF", "Zamfara State"),
]

CANONICAL_PROGRAM_DOMAINS = {
    "regular_services": {
        "name": "Regular Services",
        "description": "Weekly and routine worship, study, workers, and leaders services.",
        "types": [
            ("sunday_worship_service", "Sunday Worship Service"),
            ("monday_bible_study", "Monday Bible Study"),
            ("thursday_revival_and_evangelical_training", "Thursday Revival and Evangelical Training"),
            ("workers_training", "Workers Training"),
            ("leaders_meeting", "Leaders Meeting"),
        ],
    },
    "retreat": {
        "name": "Retreat",
        "description": "Regional or occasional retreat-focused programs.",
        "types": [
            ("easter_retreat", "Easter Retreat"),
            ("december_retreat", "December Retreat"),
            ("faith_clinic", "Faith Clinic"),
            ("seminar", "Seminar"),
        ],
    },
    "open_crusade": {
        "name": "Open Crusade",
        "description": "Monthly crusade and outreach program family.",
        "types": [
            ("impact_academy", "Impact Academy"),
            ("global_sunday", "Global Sunday"),
            ("evening_crusade", "Evening Crusade"),
        ],
    },
    "special_programs": {
        "name": "Special Programs",
        "description": "Irregular major programs that do not fit routine service, retreat, or crusade cycles.",
        "types": [
            ("workers_conference", "Workers Conference"),
            ("leaders_strategic_conference", "Leaders Strategic Conference"),
        ],
    },
}


@dataclass(frozen=True)
class StarterAccount:
    name: str
    role_name: str
    phone: str
    email: str


STARTER_ACCOUNTS = [
    StarterAccount("Pastor Samuel Adebayo", "Location Pastor", "09029952120", "samuel.adebayo@admin.dclm.ng"),
    StarterAccount("Pastor Deborah Yusuf", "Group Pastor", "09029952121", "deborah.yusuf@admin.dclm.ng"),
    StarterAccount("Pastor David Akinwale", "Region Pastor", "09029952122", "david.akinwale@admin.dclm.ng"),
    StarterAccount("Pastor Grace Omoniyi", "State Overseer", "09029952123", "grace.omoniyi@admin.dclm.ng"),
    StarterAccount("Pastor John Fasanmi", "National Admin", "09029952124", "john.fasanmi@admin.dclm.ng"),
    StarterAccount("Pastor Ruth Balogun", "Continental Admin", "09029952125", "ruth.balogun@admin.dclm.ng"),
    StarterAccount("Pastor Michael Ojo", "Global Admin", "09029952126", "michael.ojo@admin.dclm.ng"),
]


async def ensure_nation(db, payload: dict) -> Nation:
    nation = await db.get(Nation, payload["nation_id"])
    if nation:
        return nation
    return await crud_nation.create(
        db,
        obj_in=NationCreate(
            nation_id=payload["nation_id"],
            continent=WEST_AFRICA_DIVISION,
            country_name=payload["country_name"],
            capital=payload.get("capital"),
            address=None,
            church_hq=None,
            national_pastor=None,
        ),
    )


async def ensure_state(db, *, state_id: str, state_name: str) -> State:
    state = await db.get(State, state_id)
    if state:
        return state
    return await crud_state.create(
        db,
        obj_in=StateCreate(
            state_id=state_id,
            nation_id="234",
            state_name=state_name,
            city=None,
            address=None,
            state_hq=None,
            state_pastor=None,
        ),
    )


async def ensure_region(db) -> Region:
    region = await db.get(Region, "ILN")
    if region:
        return region
    return await crud_region.create(
        db,
        obj_in=RegionCreate(
            region_id="ILN",
            state_id="KW",
            region_name="Ilorin Region",
            region_head=None,
            regional_pastor=None,
        ),
    )


async def ensure_group(db) -> Group:
    group = await db.get(Group, "ILE")
    if group:
        return group
    return await crud_group.create(
        db,
        obj_in=GroupCreate(
            group_id="ILE",
            region_id="ILN",
            group_name="Ilorin East Group",
            group_head=None,
            group_pastor=None,
        ),
    )


async def ensure_location(db) -> Location:
    location = await db.get(Location, "001")
    if location:
        return location
    return await crud_location.create(
        db,
        obj_in=LocationCreate(
            location_id="001",
            group_id="ILE",
            location_name="Living Spring Lajolo",
            church_type="DLBC",
            address="Lajolo, Ilorin, Kwara State",
            associate_cord=None,
            latitude=None,
            longitude=None,
        ),
    )




async def ensure_program_metadata(db) -> None:
    for domain_slug, payload in CANONICAL_PROGRAM_DOMAINS.items():
        stmt = select(ProgramDomain).where(ProgramDomain.slug == domain_slug)
        domain = (await db.execute(stmt)).scalars().first()
        if not domain:
            domain = ProgramDomain(slug=domain_slug, name=payload["name"], description=payload.get("description"))
            db.add(domain)
            await db.commit()
            await db.refresh(domain)
        else:
            changed = False
            if domain.name != payload["name"]:
                domain.name = payload["name"]
                changed = True
            if domain.description != payload.get("description"):
                domain.description = payload.get("description")
                changed = True
            if changed:
                db.add(domain)
                await db.commit()
                await db.refresh(domain)

        for type_slug, type_name in payload["types"]:
            type_stmt = select(ProgramType).where(ProgramType.slug == type_slug)
            program_type = (await db.execute(type_stmt)).scalars().first()
            if not program_type:
                program_type = ProgramType(slug=type_slug, name=type_name, domain_id=domain.id)
                db.add(program_type)
                await db.commit()
                continue
            changed = False
            if program_type.name != type_name:
                program_type.name = type_name
                changed = True
            if program_type.domain_id != domain.id:
                program_type.domain_id = domain.id
                changed = True
            if changed:
                db.add(program_type)
                await db.commit()

async def ensure_role_map(db) -> dict[str, Role]:
    result = await db.execute(select(Role))
    roles = result.scalars().all()
    return {role.role_name: role for role in roles}


async def ensure_worker(db, account: StarterAccount, location: Location) -> Worker:
    now = datetime.now(UTC)
    existing_result = await db.execute(
        select(Worker).where((Worker.email == account.email) | (Worker.phone == account.phone))
    )
    worker = existing_result.scalars().first()
    public_code = generate_public_person_code("Kwara State", account.phone)
    if worker:
        worker.location_id = location.location_id
        worker.location_name = location.location_name
        worker.church_type = location.church_type
        worker.state = "Kwara State"
        worker.region = "Ilorin Region"
        worker.group = "Ilorin East Group"
        worker.name = account.name
        worker.gender = "Male" if account.name not in {"Pastor Deborah Yusuf", "Pastor Grace Omoniyi", "Pastor Ruth Balogun"} else "Female"
        worker.email = account.email
        worker.phone = account.phone
        worker.address = "Lajolo, Ilorin, Kwara State"
        worker.occupation = "Pastor"
        worker.marital_status = "Married"
        worker.unit = "Pastorate"
        worker.status = "Active"
        worker.approval_status = "approved"
        worker.approved_at = worker.approved_at or now
        worker.rejection_reason = None
        worker.path = str(location.path)
        if not worker.user_id or worker.user_id.startswith("W"):
            worker.user_id = public_code
        db.add(worker)
        await db.commit()
        await db.refresh(worker)
        return worker

    worker = Worker(
        user_id=public_code,
        location_id=location.location_id,
        location_name=location.location_name,
        church_type=location.church_type,
        state="Kwara State",
        region="Ilorin Region",
        group="Ilorin East Group",
        name=account.name,
        gender="Male" if account.name not in {"Pastor Deborah Yusuf", "Pastor Grace Omoniyi", "Pastor Ruth Balogun"} else "Female",
        phone=account.phone,
        email=account.email,
        address="Lajolo, Ilorin, Kwara State",
        occupation="Pastor",
        marital_status="Married",
        unit="Pastorate",
        status="Active",
        approval_status="approved",
        approved_at=now,
        path=str(location.path),
    )
    db.add(worker)
    await db.commit()
    await db.refresh(worker)
    return worker


async def ensure_user(db, worker: Worker, role: Role, password: str, reset_passwords: bool) -> User:
    now = datetime.now(UTC)
    existing_result = await db.execute(select(User).options(selectinload(User.roles)).where(User.worker_id == worker.worker_id))
    user = existing_result.scalars().first()
    if user:
        user.name = worker.name
        user.phone = worker.phone
        user.email = worker.email
        user.location_id = worker.location_id
        user.path = worker.path
        user.is_active = True
        user.approval_status = "approved"
        user.approved_at = user.approved_at or now
        user.rejection_reason = None
        if reset_passwords:
            user.password = hash_password(password)
        user.roles = [role]
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    user = User(
        worker_id=worker.worker_id,
        password=hash_password(password),
        is_active=True,
        approval_status="approved",
        approved_at=now,
        location_id=worker.location_id,
        name=worker.name,
        phone=worker.phone,
        email=worker.email,
        path=worker.path,
        roles=[role],
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def seed_metadata_only() -> None:
    """Seed safe metadata without creating hierarchy records or starter users."""
    async with AsyncSessionLocal() as db:
        await init_rbac(db)
        await ensure_program_metadata(db)
        await db.commit()
    print("Metadata seed complete: RBAC roles, permissions, role scores, and program metadata are ready.")


async def run(password: str, reset_passwords: bool, metadata_only: bool = False) -> None:
    if metadata_only:
        await seed_metadata_only()
        return

    async with AsyncSessionLocal() as db:
        existing_roles = (await db.execute(select(Role.role_name))).scalars().all()
        if existing_roles:
            print("RBAC roles already exist; skipping full RBAC reseed for bootstrap.")
        else:
            await init_rbac(db)

        for nation_payload in WEST_AFRICA_NATIONS:
            await ensure_nation(db, nation_payload)

        for state_id, state_name in NIGERIA_STATES:
            await ensure_state(db, state_id=state_id, state_name=state_name)

        await ensure_region(db)
        await ensure_group(db)
        location = await ensure_location(db)
        await ensure_program_metadata(db)
        role_map = await ensure_role_map(db)

        missing_roles = [account.role_name for account in STARTER_ACCOUNTS if account.role_name not in role_map]
        if missing_roles:
            raise RuntimeError(f"Missing roles after RBAC seed: {', '.join(sorted(set(missing_roles)))}")

        seeded = []
        for account in STARTER_ACCOUNTS:
            worker = await ensure_worker(db, account, location)
            user = await ensure_user(db, worker, role_map[account.role_name], password, reset_passwords)
            scope_id = generate_display_id(str(user.path))
            seeded.append(
                {
                    "name": account.name,
                    "role": account.role_name,
                    "email": account.email,
                    "phone": account.phone,
                    "worker_code": worker.user_id,
                    "scope_id": scope_id,
                }
            )

        print("\nSeed complete. Starter accounts ready:\n")
        for row in seeded:
            print(f"- {row['role']}: {row['name']}")
            print(f"  email: {row['email']}")
            print(f"  password: {password}")
            print(f"  worker code: {row['worker_code']}")
            print(f"  home scope: {row['scope_id']}")
        print("\nSeeded Kwara starter path: DCM-234-KW-ILN-ILE-001")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed West Africa hierarchy, Nigeria states, and starter pastor accounts.")
    parser.add_argument(
        "--password",
        default=None,
        help="Initial password for all seeded starter accounts. If omitted, a strong temporary password is generated.",
    )
    parser.add_argument(
        "--reset-passwords",
        action="store_true",
        help="Reset passwords for existing starter users to the supplied password.",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Seed RBAC and program metadata only; do not create hierarchy records, workers, or users.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    password = args.password or secrets.token_urlsafe(18)

    async def main() -> None:
        try:
            await run(password=password, reset_passwords=args.reset_passwords, metadata_only=args.metadata_only)
        finally:
            await engine.dispose()

    asyncio.run(main())
