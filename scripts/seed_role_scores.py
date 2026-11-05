"""
Seed role scores (1-9).

Run:
  python scripts/seed_role_scores.py
"""
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import AsyncSessionLocal, engine
from app.models.user import RoleScore


ROLE_SCORES = [
    {
        "score": 1,
        "score_name": "Church Worker / Usher",
        "description": "Field worker or usher. This app grants only assigned collection permissions at this level.",
    },
    {
        "score": 2,
        "score_name": "Location Pastor",
        "description": "Location-level pastor responsible for one physical location.",
    },
    {
        "score": 3,
        "score_name": "Group Pastor",
        "description": "Group-level pastor responsible for locations in one group.",
    },
    {
        "score": 4,
        "score_name": "Regional Pastor",
        "description": "Region-level pastor responsible for groups in one region.",
    },
    {
        "score": 5,
        "score_name": "State Pastor / Overseer",
        "description": "State-level pastor responsible for regions in one state.",
    },
    {
        "score": 6,
        "score_name": "Zonal Coordinator",
        "description": "Reserved zonal leadership; scope awaits the church's zone-to-hierarchy mapping.",
    },
    {
        "score": 7,
        "score_name": "National Overseer",
        "description": "National leadership; overrides state-level authority within the assigned nation.",
    },
    {
        "score": 8,
        "score_name": "Continental Leader",
        "description": "Continental and general administration; overrides national and state authority within the assigned continent.",
    },
    {
        "score": 9,
        "score_name": "General Overseer / Global Admin",
        "description": "Super-administrator and superintendent with global authority.",
    },
]


async def seed_role_scores() -> None:
    created = 0
    updated = 0

    async with AsyncSessionLocal() as db:
        for data in ROLE_SCORES:
            existing = (await db.execute(
                select(RoleScore).where(RoleScore.score == data["score"])
            )).scalars().first()

            if existing:
                changed = False
                if existing.score_name != data["score_name"]:
                    existing.score_name = data["score_name"]
                    changed = True
                if existing.description != data["description"]:
                    existing.description = data["description"]
                    changed = True
                if changed:
                    db.add(existing)
                    updated += 1
            else:
                db.add(RoleScore(**data))
                created += 1

        await db.commit()

    print(f"Role scores created: {created}")
    print(f"Role scores updated: {updated}")


if __name__ == "__main__":
    async def main() -> None:
        try:
            await seed_role_scores()
        finally:
            await engine.dispose()

    asyncio.run(main())
