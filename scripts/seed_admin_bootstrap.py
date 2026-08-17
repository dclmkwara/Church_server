from __future__ import annotations

import argparse
import asyncio
import re
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
CHURCH_ACRONYM = "DCM"
NIGERIA_NATION_ID = "234"
KWARA_STATE_ID = "KW"
DEFAULT_STARTER_LOCATION_ID = "003"

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
    gender: str = "Male"
    unit: str = "Pastorate"
    occupation: str = "Pastor"


@dataclass(frozen=True)
class SeedLocation:
    location_code: str
    location_name: str
    church_type: str
    address: str


ILORIN_REGION_NAME = "Ilorin Region"
ILORIN_EAST_GROUP_NAME = "Ilorin East Group"
KNOWN_REGION_CODES = {
    ILORIN_REGION_NAME.casefold(): "ILR",
}
KNOWN_GROUP_CODES = {
    ILORIN_EAST_GROUP_NAME.casefold(): "ILE",
}
IGNORED_CODE_WORDS = {
    "AREA",
    "BRANCH",
    "CAMPUS",
    "CHURCH",
    "DCLC",
    "DLCF",
    "DLSO",
    "DLBC",
    "GROUP",
    "LIFE",
    "REGION",
}

ILORIN_EAST_LOCATIONS = [
    SeedLocation(
        location_code="001",
        location_name="DLCF Kwara Poly",
        church_type="DLCF",
        address="Kwara State Polytechnic, Ilorin, Kwara State",
    ),
    SeedLocation(
        location_code="002",
        location_name="DLCF College",
        church_type="DLCF",
        address="Agbede, Kwara State",
    ),
    SeedLocation(
        location_code="003",
        location_name="DLCF Living Spring",
        church_type="DLCF",
        address="Lajolo, Kwara State",
    ),
    SeedLocation(
        location_code="004",
        location_name="DLCF Day Spring",
        church_type="DLCF",
        address="Oke-Ose, Kwara State",
    ),
]


STARTER_ACCOUNTS = [
    StarterAccount(
        "Brother Daniel Olanrewaju",
        "House Fellowship Leader",
        "09029952118",
        "fellowship.leader@admin.dclm.ng",
        unit="Home Care Fellowship",
        occupation="Fellowship Leader",
    ),
    StarterAccount(
        "Sister Mary Ojo",
        "Location Worker",
        "09029952119",
        "location.worker@admin.dclm.ng",
        gender="Female",
        unit="Follow Up",
        occupation="Church Worker",
    ),
    StarterAccount("Pastor Samuel Adebayo", "Location Pastor", "09029952120", "location.pastor@admin.dclm.ng"),
    StarterAccount("Pastor Deborah Yusuf", "Group Pastor", "09029952121", "group.pastor@admin.dclm.ng", gender="Female"),
    StarterAccount("Pastor David Akinwale", "Region Pastor", "09029952122", "region.pastor@admin.dclm.ng"),
    StarterAccount("Pastor Grace Omoniyi", "State Overseer", "09029952123", "state.overseer@admin.dclm.ng", gender="Female"),
    StarterAccount("Pastor John Fasanmi", "National Admin", "09029952124", "national.admin@admin.dclm.ng"),
    StarterAccount("Pastor Ruth Balogun", "Continental Admin", "09029952125", "continental.admin@admin.dclm.ng", gender="Female"),
    StarterAccount("Meshell Eva", "Global Admin", "09029952126", "meshelleva@gmail.com"),
]


def _clean_code_word(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _meaningful_code_words(name: str) -> list[str]:
    words = [_clean_code_word(word) for word in re.split(r"\s+", name.strip())]
    return [word for word in words if word and word not in IGNORED_CODE_WORDS]


def derive_hierarchy_code(name: str, *, level: str) -> str:
    """Derive a stable 3-character hierarchy code before collision checks."""
    level_key = level.casefold()
    known_codes = KNOWN_REGION_CODES if level_key == "region" else KNOWN_GROUP_CODES
    known_code = known_codes.get(name.casefold())
    if known_code:
        return known_code

    words = _meaningful_code_words(name)
    if not words:
        raise ValueError(f"Cannot derive {level} code from empty name")

    if len(words) >= 2:
        code = f"{words[0][:2]}{words[1][0]}"
    else:
        suffix = "R" if level_key == "region" else "G"
        code = f"{words[0][:2]}{suffix}"
    return code[:3].ljust(3, "X")


async def generate_available_hierarchy_code(db, model, code_attr: str, parent_filter, name: str, *, level: str) -> str:
    base_code = derive_hierarchy_code(name, level=level)
    candidates = [base_code]
    code_seed = _clean_code_word("".join(_meaningful_code_words(name)))
    for index in range(len(code_seed)):
        candidates.append((base_code[:2] + code_seed[index])[:3])
    for index in range(10):
        candidates.append(f"{base_code[:2]}{index}")

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        code_column = getattr(model, code_attr)
        existing = (
            await db.execute(select(model).where(parent_filter, code_column == candidate))
        ).scalars().first()
        if not existing:
            return candidate

    raise RuntimeError(f"Could not generate an available {level} code for {name!r}")


def formatted_path(path: object) -> str:
    return f"{CHURCH_ACRONYM}-{str(path).replace('org.', '').replace('.', '-')}"


async def ensure_nation(db, payload: dict) -> Nation:
    nation = (
        await db.execute(select(Nation).where(Nation.nation_code == payload["nation_id"]))
    ).scalars().first()
    if nation:
        return nation
    return await crud_nation.create(
        db,
        obj_in=NationCreate(
            nation_code=payload["nation_id"],
            continent=WEST_AFRICA_DIVISION,
            country_name=payload["country_name"],
            capital=payload.get("capital"),
            address=None,
            church_hq=None,
            national_pastor=None,
        ),
    )


async def ensure_state(db, *, nation: Nation, state_code: str, state_name: str) -> State:
    state = (
        await db.execute(
            select(State).where(State.nation_id == nation.nation_id, State.state_code == state_code)
        )
    ).scalars().first()
    if state:
        return state
    return await crud_state.create(
        db,
        obj_in=StateCreate(
            state_code=state_code,
            nation_id=nation.nation_id,
            state_name=state_name,
            city=None,
            address=None,
            state_hq=None,
            state_pastor=None,
        ),
    )


async def ensure_region(db, kwara_state: State) -> Region:
    desired_code = derive_hierarchy_code(ILORIN_REGION_NAME, level="region")
    region = (
        await db.execute(
            select(Region).where(
                Region.state_id == kwara_state.state_id,
                Region.region_code == desired_code,
            )
        )
    ).scalars().first()
    if region:
        region.region_name = ILORIN_REGION_NAME
        region.path = f"{kwara_state.path}.{region.region_code}"
        db.add(region)
        await db.commit()
        await db.refresh(region)
        return region

    existing_by_name = (
        await db.execute(
            select(Region).where(
                Region.state_id == kwara_state.state_id,
                Region.region_name == ILORIN_REGION_NAME,
            )
        )
    ).scalars().first()
    if existing_by_name:
        print(
            f"Using existing region {existing_by_name.region_id} for {ILORIN_REGION_NAME}; "
            f"new deployments will use {desired_code}."
        )
        return existing_by_name

    region_code = await generate_available_hierarchy_code(
        db,
        Region,
        "region_code",
        Region.state_id == kwara_state.state_id,
        ILORIN_REGION_NAME,
        level="region",
    )
    return await crud_region.create(
        db,
        obj_in=RegionCreate(
            region_code=region_code,
            state_id=kwara_state.state_id,
            region_name=ILORIN_REGION_NAME,
            region_head=None,
            regional_pastor=None,
        ),
    )


async def ensure_group(db, region: Region) -> Group:
    desired_code = derive_hierarchy_code(ILORIN_EAST_GROUP_NAME, level="group")
    group = (
        await db.execute(
            select(Group).where(Group.region_id == region.region_id, Group.group_code == desired_code)
        )
    ).scalars().first()
    if group:
        group.group_name = ILORIN_EAST_GROUP_NAME
        group.path = f"{region.path}.{group.group_code}"
        db.add(group)
        await db.commit()
        await db.refresh(group)
        return group

    existing_by_name = (
        await db.execute(
            select(Group).where(
                Group.region_id == region.region_id,
                Group.group_name == ILORIN_EAST_GROUP_NAME,
            )
        )
    ).scalars().first()
    if existing_by_name:
        print(
            f"Using existing group {existing_by_name.group_id} for {ILORIN_EAST_GROUP_NAME}; "
            f"new deployments will use {desired_code}."
        )
        return existing_by_name

    group_code = await generate_available_hierarchy_code(
        db,
        Group,
        "group_code",
        Group.region_id == region.region_id,
        ILORIN_EAST_GROUP_NAME,
        level="group",
    )
    return await crud_group.create(
        db,
        obj_in=GroupCreate(
            group_code=group_code,
            region_id=region.region_id,
            group_name=ILORIN_EAST_GROUP_NAME,
            group_head=None,
            group_pastor=None,
        ),
    )


async def ensure_location(db, group: Group, payload: SeedLocation) -> Location:
    location = (
        await db.execute(
            select(Location).where(
                Location.group_id == group.group_id,
                Location.location_code == payload.location_code,
            )
        )
    ).scalars().first()
    if location:
        location.location_name = payload.location_name
        location.church_type = payload.church_type
        location.address = payload.address
        location.path = f"{group.path}.{payload.location_code}"
        db.add(location)
        await db.commit()
        await db.refresh(location)
        return location
    return await crud_location.create(
        db,
        obj_in=LocationCreate(
            location_code=payload.location_code,
            group_id=group.group_id,
            location_name=payload.location_name,
            church_type=payload.church_type,
            address=payload.address,
            associate_cord=None,
            latitude=None,
            longitude=None,
        ),
    )


async def ensure_ilorin_east_locations(db, group: Group) -> dict[str, Location]:
    locations = {}
    for payload in ILORIN_EAST_LOCATIONS:
        location = await ensure_location(db, group, payload)
        locations[location.location_code] = location
    return locations




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
        worker.gender = account.gender
        worker.email = account.email
        worker.phone = account.phone
        worker.address = location.address
        worker.occupation = account.occupation
        worker.marital_status = "Married"
        worker.unit = account.unit
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
        gender=account.gender,
        phone=account.phone,
        email=account.email,
        address=location.address,
        occupation=account.occupation,
        marital_status="Married",
        unit=account.unit,
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

        nations = {}
        for nation_payload in WEST_AFRICA_NATIONS:
            nation = await ensure_nation(db, nation_payload)
            nations[nation.nation_code] = nation

        nigeria = nations[NIGERIA_NATION_ID]

        states = {}
        for state_code, state_name in NIGERIA_STATES:
            state = await ensure_state(db, nation=nigeria, state_code=state_code, state_name=state_name)
            states[state.state_code] = state

        region = await ensure_region(db, states[KWARA_STATE_ID])
        group = await ensure_group(db, region)
        locations = await ensure_ilorin_east_locations(db, group)
        location = locations[DEFAULT_STARTER_LOCATION_ID]
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
        print("\nSeeded Ilorin East locations:")
        for seeded_location in locations.values():
            print(f"- {seeded_location.location_code}: {seeded_location.location_name} ({seeded_location.address})")
        print(f"\nSeeded Kwara starter path: {formatted_path(location.path)}")


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
