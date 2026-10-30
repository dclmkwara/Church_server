"""
Tests for Bulk Import / Export feature.
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


def test_code_generators():
    """Verify initials-based code generation for regions and groups."""
    assert generate_region_code("Ilorin Region") == "ILR"
    assert generate_region_code("Kwara") == "KWA"
    assert generate_group_code("Ilorin East") == "ILE"
    assert generate_group_code("Ilorin West") == "ILW"
    assert generate_group_code("Central") == "CEN"
    assert generate_group_code("North Central Region") == "NCR"


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
