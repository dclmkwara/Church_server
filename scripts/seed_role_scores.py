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
        "score_name": "Level 1",
        "description": "Least level in the church (ordinary usher / basic worker at location).",
    },
    {
        "score": 2,
        "score_name": "Level 2",
        "description": "Special responsibilities at location level (general coordinator, financial secretary, sister welfare, etc.).",
    },
    {
        "score": 3,
        "score_name": "Level 3",
        "description": "Highest location-level authority (location pastor).",
    },
    {
        "score": 4,
        "score_name": "Level 4",
        "description": "Group level leadership and key positions (group pastors and group officials).",
    },
    {
        "score": 5,
        "score_name": "Level 5",
        "description": "Region level leadership and key positions (regional pastors and officials).",
    },
    {
        "score": 6,
        "score_name": "Level 6",
        "description": "State level leadership and key positions (state pastors and officials).",
    },
    {
        "score": 7,
        "score_name": "Level 7",
        "description": "National level leadership and key positions.",
    },
    {
        "score": 8,
        "score_name": "Level 8",
        "description": "General church admin level leadership.",
    },
    {
        "score": 9,
        "score_name": "Level 9",
        "description": "Highest level (super admin & General Superintendents) with all system rights.",
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
