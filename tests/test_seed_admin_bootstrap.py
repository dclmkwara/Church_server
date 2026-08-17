import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-suite-32-chars-min")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import seed_admin_bootstrap as seed


def test_known_ilorin_codes_are_stable():
    assert seed.derive_hierarchy_code("Ilorin Region", level="region") == "ILR"
    assert seed.derive_hierarchy_code("Ilorin East Group", level="group") == "ILE"


def test_seed_locations_include_living_spring_as_003():
    locations = {location.location_code: location for location in seed.ILORIN_EAST_LOCATIONS}

    assert set(locations) == {"001", "002", "003", "004"}
    assert locations["001"].location_name == "DLCF Kwara Poly"
    assert locations["002"].address == "Agbede, Kwara State"
    assert locations["003"].location_name == "DLCF Living Spring"
    assert locations["004"].address == "Oke-Ose, Kwara State"


def test_starter_accounts_cover_level_one_to_super_admin_roles():
    expected_roles = [
        "House Fellowship Leader",
        "Location Worker",
        "Location Pastor",
        "Group Pastor",
        "Region Pastor",
        "State Overseer",
        "National Admin",
        "Continental Admin",
        "Global Admin",
    ]

    assert [account.role_name for account in seed.STARTER_ACCOUNTS] == expected_roles
    assert len({account.email for account in seed.STARTER_ACCOUNTS}) == len(expected_roles)
    assert len({account.phone for account in seed.STARTER_ACCOUNTS}) == len(expected_roles)


@pytest.mark.asyncio
async def test_generated_code_skips_existing_primary_key():
    class FakeResult:
        def __init__(self, value):
            self.value = value

        def scalars(self):
            return self

        def first(self):
            return self.value

    class FakeDb:
        def __init__(self):
            self.calls = 0

        async def execute(self, stmt):
            self.calls += 1
            return FakeResult(object() if self.calls == 1 else None)

    code = await seed.generate_available_hierarchy_code(
        FakeDb(),
        seed.Region,
        "region_code",
        seed.Region.state_id == "state-id",
        "Ilorin Region",
        level="region",
    )

    assert code != "ILR"
    assert len(code) == 3
