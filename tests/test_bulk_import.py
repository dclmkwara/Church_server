"""
Tests for Bulk Import / Export feature and Collision-Safe Code Generation.
"""
import io
from unittest.mock import AsyncMock, MagicMock
import pytest
from openpyxl import load_workbook

from app.services.bulk_import_service import (
    generate_group_code,
    generate_hierarchy_template,
    generate_region_code,
    generate_workers_template,
    parse_and_validate_hierarchy,
    parse_and_validate_workers,
)


def test_code_generators_standard():
    """Verify standard region and group codes."""
    assert generate_region_code("Ilorin Region") == "ILR"
    assert generate_region_code("Offa Region") == "OFR"
    assert generate_region_code("Omu-Aran Region") == "OAR"
    assert generate_region_code("Kwara South Region") == "KSR"
    assert generate_group_code("Ilorin East") == "ILE"
    assert generate_group_code("Ilorin West") == "ILW"
    assert generate_group_code("Central Group") == "CEN"


def test_code_generators_hyphenated_and_critical_cases():
    """
    Critical conditions:
    1. 'Asa Group' vs 'Asa-dam group':
       - 'Asa Group' strips 'group' -> 'Asa' -> 'ASA'
       - 'Asa-dam group' splits on hyphen -> ['Asa', 'dam'] -> 'ASD'
    2. Punctuated, single-token, and short names.
    """
    asa_code = generate_group_code("Asa Group")
    asadam_code = generate_group_code("Asa-dam group")
    assert asa_code == "ASA"
    assert asadam_code == "ASD"
    assert asa_code != asadam_code

    # Hyphenated place names
    assert generate_group_code("Offa-Garage Group") == "OFG"
    assert generate_group_code("Oja-Tuntun Group") == "OJT"
    assert generate_group_code("St. Jude Group") == "STJ"

    # Short / single-word names
    assert generate_group_code("GRA Group") == "GRA"
    assert generate_group_code("Oja Group") == "OJA"
    assert generate_group_code("A Group") == "AXX"
    assert generate_group_code("DB Group") == "DBX"


def test_collision_resolution_group_codes():
    """
    Verify that when candidate codes collide, the algorithm automatically
    disambiguates them using alternative word characters or numeric suffixes.
    """
    existing: set[str] = set()

    # 'Ilorin East' gets 'ILE'
    c1 = generate_group_code("Ilorin East", existing_codes=existing)
    assert c1 == "ILE"
    existing.add(c1)

    # 'Iludun East' would normally get 'ILE', but 'ILE' is taken -> should vary to 'IUE'
    c2 = generate_group_code("Iludun East", existing_codes=existing)
    assert c2 != "ILE"
    assert c2 not in existing
    assert c2 == "IUE"
    existing.add(c2)

    # 'Ilesha East' -> 'IEE'
    c3 = generate_group_code("Ilesha East", existing_codes=existing)
    assert c3 not in existing
    existing.add(c3)

    # Passing 'Ilorin East' again produces letter variation 'IOE', avoiding 'ILE'
    c4 = generate_group_code("Ilorin East", existing_codes=existing)
    assert c4 not in existing
    assert c4 == "IOE"
    existing.add(c4)

    # Exhaust all letter variations to verify numeric fallback (e.g. 'IL2', 'IL3')
    for _ in range(20):
        code = generate_group_code("Ilorin East", existing_codes=existing)
        assert code not in existing
        existing.add(code)
    # Verify that a numeric suffix was used once letters were exhausted
    has_numeric = any(any(ch.isdigit() for ch in c) for c in existing)
    assert has_numeric


def test_collision_resolution_region_codes():
    """Verify region code collision resolution."""
    existing = {"ILR"}
    # Another region that might collide with 'ILR'
    c = generate_region_code("Ilorin Central Region", existing_codes=existing)
    assert c != "ILR"
    assert c not in existing
    assert c == "ICR"


def test_hierarchy_template_structure():
    """Verify that generated hierarchy template contains all required sheets and headers."""
    xlsx_bytes = generate_hierarchy_template()
    assert len(xlsx_bytes) > 1000

    wb = load_workbook(io.BytesIO(xlsx_bytes))
    assert "Instructions" in wb.sheetnames
    assert "Regions" in wb.sheetnames
    assert "Groups" in wb.sheetnames
    assert "Locations" in wb.sheetnames

    # Check Regions sheet headers
    ws_reg = wb["Regions"]
    headers = [cell.value for cell in ws_reg[1]]
    assert "Region Name" in headers

    # Check Locations sheet headers
    ws_loc = wb["Locations"]
    loc_headers = [cell.value for cell in ws_loc[1]]
    assert "Location Name" in loc_headers
    assert "Church Type (DLBC/DLCF/DLSO)" in loc_headers


def test_workers_template_structure():
    """Verify that generated workers template has correct sheet and columns."""
    xlsx_bytes = generate_workers_template()
    assert len(xlsx_bytes) > 1000

    wb = load_workbook(io.BytesIO(xlsx_bytes))
    assert "Workers" in wb.sheetnames
    ws = wb["Workers"]
    headers = [cell.value for cell in ws[1]]
    assert "Full Name" in headers
    assert "Phone" in headers
    assert "Email" in headers
    assert "Location Name (exact)" in headers
    assert "Unit (e.g. Ushering, Choir)" in headers


@pytest.mark.asyncio
async def test_validate_hierarchy_empty_file():
    """Dry-run validation on an invalid/empty file should report errors."""
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_res

    result = await parse_and_validate_hierarchy(b"not a real file", "non-existent-state", mock_session)
    assert not result.is_valid
    assert len(result.errors) > 0


@pytest.mark.asyncio
async def test_validate_workers_empty_file():
    """Dry-run validation on an invalid file should report errors."""
    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.all.return_value = []
    mock_res.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_res

    result = await parse_and_validate_workers(b"invalid data", mock_session)
    assert not result.is_valid
    assert len(result.errors) > 0
