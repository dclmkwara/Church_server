"""
Bulk Import / Export Service for DCL Church Management System.

Provides:
- Excel (.xlsx) and CSV template generation (hierarchy & workers)
- Multi-sheet and flat-sheet parsing
- Dry-run validation with duplicate detection (in-file and in-DB)
- Atomic DB commit for hierarchy and workers
- Auto-code generation (region, group, location codes)
"""
from __future__ import annotations

import csv
import io
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Group, Location, Nation, Region, State
from app.models.user import Worker

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Code generation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _initials(name: str, length: int = 3) -> str:
    """
    Derive an uppercase alphabetic code from a church entity name.

    Convention:
      - 3+ words: take 1st letter of first 3 words (e.g. 'North Central Region' -> 'NCR')
      - 2 words: take 2 letters of 1st word + 1st letter of 2nd (e.g. 'Ilorin Region' -> 'ILR', 'Ilorin East' -> 'ILE')
      - 1 word: take first 3 letters (e.g. 'Kwara' -> 'KWA', 'Central' -> 'CEN')
    """
    words = [re.sub(r"[^a-zA-Z0-9]", "", w) for w in name.split() if re.sub(r"[^a-zA-Z0-9]", "", w)]
    if not words:
        return "UNK"
    if len(words) >= 3:
        code = "".join(w[0] for w in words[:3])
    elif len(words) == 2:
        code = words[0][:2] + words[1][:1]
    else:
        code = words[0][:3]
    return code.upper().ljust(length, "X")[:length]


def generate_region_code(region_name: str) -> str:
    """Generate 3-letter region code from name, e.g. 'Ilorin Region' -> 'ILR'."""
    return _initials(region_name, 3)


def generate_group_code(group_name: str) -> str:
    """Generate 3-letter group code from name, e.g. 'Ilorin East' -> 'ILE'."""
    return _initials(group_name, 3)


async def next_location_code(db: AsyncSession, group_id: str) -> str:
    """Return next sequential 3-digit location code for a group, e.g. '001', '005'."""
    result = await db.execute(
        select(Location.location_code).where(Location.group_id == group_id)
    )
    codes = [r for r in result.scalars().all() if r and r.isdigit()]
    if not codes:
        return "001"
    return f"{max(int(c) for c in codes) + 1:03d}"


# ─────────────────────────────────────────────────────────────────────────────
# Excel styling helpers
# ─────────────────────────────────────────────────────────────────────────────

_HEADER_FILL = PatternFill("solid", fgColor="1A3557")
_HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
_BORDER = Border(
    left=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin", color="CCCCCC"),
    top=Side(style="thin", color="CCCCCC"),
    bottom=Side(style="thin", color="CCCCCC"),
)
_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _style_header_row(ws, headers: list[tuple[str, bool]]) -> None:
    ws.row_dimensions[1].height = 30
    ws.row_dimensions[2].height = 20
    for col_idx, (label, required) in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=label)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _CENTER
        cell.border = _BORDER
        note = ws.cell(row=2, column=col_idx, value="(required)" if required else "(optional)")
        note.font = Font(italic=True, size=9, color="777777")
        note.alignment = _CENTER


def _set_col_widths(ws, widths: list[int]) -> None:
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


# ─────────────────────────────────────────────────────────────────────────────
# Template generators
# ─────────────────────────────────────────────────────────────────────────────

def generate_hierarchy_template() -> bytes:
    """Generate an Excel workbook for bulk hierarchy import."""
    wb = Workbook()

    # Sheet 1: Instructions
    ws_info = wb.active
    ws_info.title = "Instructions"
    ws_info["A1"] = "DCL Church Hierarchy Bulk Import Template"
    ws_info["A1"].font = Font(bold=True, size=14, color="1A3557")
    instructions = [
        ("Instructions for Admin:", True),
        ("1. Fill in the REGIONS sheet with all regions in your state.", False),
        ("2. Fill in the GROUPS sheet with all groups, referencing Region Name exactly.", False),
        ("3. Fill in the LOCATIONS sheet with all locations, referencing Group Name exactly.", False),
        ("4. Region Code & Group Code are optional — leaving them blank auto-generates 3-letter codes.", False),
        ("5. Location Code is automatically generated sequentially (001, 002, …).", False),
        ("6. Church Type must be DLBC, DLCF, or DLSO.", False),
        ("7. Upload via 'Import Hierarchy' in the Admin Organization view.", False),
    ]
    for row_idx, (text, bold) in enumerate(instructions, start=2):
        cell = ws_info.cell(row=row_idx, column=1, value=text)
        cell.font = Font(bold=bold, size=10)
    ws_info.column_dimensions["A"].width = 85

    # Sheet 2: Regions
    ws_reg = wb.create_sheet("Regions")
    _style_header_row(ws_reg, [
        ("Region Name", True),
        ("Region Code (auto if blank)", False),
        ("Regional Pastor", False),
        ("Region Head", False),
    ])
    _set_col_widths(ws_reg, [30, 24, 30, 30])
    for col, val in enumerate(["Ilorin Region", "ILR", "Pastor A. Adeyemi", "Bro. Adewale"], start=1):
        cell = ws_reg.cell(row=3, column=col, value=val)
        cell.font = Font(italic=True, color="888888", size=9)
    ws_reg.freeze_panes = "A3"

    # Sheet 3: Groups
    ws_grp = wb.create_sheet("Groups")
    _style_header_row(ws_grp, [
        ("Region Name (must match Regions sheet)", True),
        ("Group Name", True),
        ("Group Code (auto if blank)", False),
        ("Group Pastor", False),
        ("Group Head", False),
    ])
    _set_col_widths(ws_grp, [34, 30, 24, 30, 30])
    for col, val in enumerate(["Ilorin Region", "Ilorin East", "ILE", "Pastor B. Alabi", ""], start=1):
        cell = ws_grp.cell(row=3, column=col, value=val)
        cell.font = Font(italic=True, color="888888", size=9)
    ws_grp.freeze_panes = "A3"

    # Sheet 4: Locations
    ws_loc = wb.create_sheet("Locations")
    _style_header_row(ws_loc, [
        ("Group Name (must match Groups sheet)", True),
        ("Location Name", True),
        ("Church Type (DLBC/DLCF/DLSO)", True),
        ("Address", False),
        ("Associate Coordinator", False),
        ("Pastor in Charge", False),
        ("Phone", False),
    ])
    _set_col_widths(ws_loc, [34, 34, 20, 36, 30, 30, 18])
    sample_locs = [
        ["Ilorin East", "DLCF Kwara Poly", "DLCF", "Kwara Poly Road, Ilorin", "", "Pastor Kunle", "08012345678"],
        ["Ilorin East", "DLCF Living Spring", "DLCF", "Living Spring Layout, Ilorin", "", "", ""],
        ["Ilorin East", "DLCF College of Health Sciences", "DLCF", "COHS Campus, Ilorin", "", "", ""],
        ["Ilorin East", "DLCF Dayspring", "DLCF", "Dayspring Estate, Ilorin", "", "", ""],
    ]
    for r, row_data in enumerate(sample_locs, start=3):
        for c, val in enumerate(row_data, start=1):
            cell = ws_loc.cell(row=r, column=c, value=val)
            cell.font = Font(italic=True, color="888888", size=9)
    ws_loc.freeze_panes = "A3"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generate_workers_template() -> bytes:
    """Generate an Excel workbook for bulk workers import."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Workers"

    worker_headers = [
        ("Full Name", True),
        ("Gender (Male/Female)", True),
        ("Phone", True),
        ("Email", True),
        ("Location Name (exact)", True),
        ("Unit (e.g. Ushering, Choir)", True),
        ("Address", False),
        ("Occupation", False),
        ("Marital Status (Single/Married/Widowed)", False),
    ]
    _style_header_row(ws, worker_headers)
    _set_col_widths(ws, [28, 22, 18, 30, 36, 22, 30, 22, 30])

    samples = [
        ["John Adeyemi", "Male", "08012345678", "john@example.com", "DLCF Kwara Poly", "Ushering", "10 Sample St", "Engineer", "Single"],
        ["Mary Alabi", "Female", "08087654321", "mary@example.com", "DLCF Living Spring", "Choir", "", "Teacher", "Married"],
    ]
    for r, row_data in enumerate(samples, start=3):
        for c, val in enumerate(row_data, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = Font(italic=True, color="888888", size=9)
    ws.freeze_panes = "A3"

    ws2 = wb.create_sheet("Instructions")
    ws2["A1"] = "DCL Workers Bulk Import Template"
    ws2["A1"].font = Font(bold=True, size=14, color="1A3557")
    notes = [
        "1. Fill in each worker row on the Workers sheet.",
        "2. Phone must be unique across the system.",
        "3. Email must be unique across the system.",
        "4. Location Name must match an existing location in the database.",
        "5. Leave optional fields blank if unknown.",
        "6. Upload via 'Import Workers' on the Workers directory page.",
    ]
    for i, note in enumerate(notes, start=2):
        ws2.cell(row=i, column=1, value=note).font = Font(size=10)
    ws2.column_dimensions["A"].width = 85

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ImportError:
    sheet: str
    row: int
    column: str
    message: str


@dataclass
class HierarchyImportResult:
    regions: list[dict[str, Any]] = field(default_factory=list)
    groups: list[dict[str, Any]] = field(default_factory=list)
    locations: list[dict[str, Any]] = field(default_factory=list)
    errors: list[ImportError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def summary(self) -> dict[str, int]:
        return {
            "regions": len(self.regions),
            "groups": len(self.groups),
            "locations": len(self.locations),
            "errors": len(self.errors),
        }


@dataclass
class WorkersImportResult:
    workers: list[dict[str, Any]] = field(default_factory=list)
    errors: list[ImportError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def summary(self) -> dict[str, int]:
        return {
            "workers": len(self.workers),
            "errors": len(self.errors),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _read_sheet(wb, sheet_name: str) -> list[list[Any]]:
    if sheet_name not in wb.sheetnames:
        return []
    ws = wb[sheet_name]
    rows = []
    for row in ws.iter_rows(min_row=3, values_only=True):
        if all(v is None or str(v).strip() == "" for v in row):
            continue
        rows.append(list(row))
    return rows


def _cell_str(row: list, idx: int) -> str:
    if idx >= len(row) or row[idx] is None:
        return ""
    return str(row[idx]).strip()


def _parse_csv_rows(content: bytes) -> list[list[str]]:
    text_data = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text_data))
    return [[col.strip() for col in row] for row in reader if any(col.strip() for col in row)]


async def _resolve_state(db: AsyncSession, state_id: str) -> State | None:
    """Safely lookup state by UUID, state_code, or state_name."""
    if not state_id:
        return None
    try:
        uuid_val = uuid.UUID(state_id)
        res = await db.execute(select(State).where(State.state_id == str(uuid_val)))
        st = res.scalars().first()
        if st:
            return st
    except (ValueError, AttributeError):
        pass

    # Lookup by state_code or state_name
    res = await db.execute(
        select(State).where(or_(State.state_code.ilike(state_id), State.state_name.ilike(state_id)))
    )
    return res.scalars().first()


# ─────────────────────────────────────────────────────────────────────────────
# Hierarchy validation
# ─────────────────────────────────────────────────────────────────────────────

async def parse_and_validate_hierarchy(
    file_bytes: bytes,
    state_id: str,
    db: AsyncSession,
    filename: str = "",
) -> HierarchyImportResult:
    """
    Parse uploaded hierarchy file (Excel multi-sheet, Excel flat, or CSV) and validate.
    """
    result = HierarchyImportResult()

    # Validate state exists in DB
    state_row = await _resolve_state(db, state_id)
    if not state_row:
        result.errors.append(ImportError("File", 0, "state_id", f"State '{state_id}' not found in database"))
        return result

    actual_state_id = str(state_row.state_id)

    # Check if CSV
    is_csv = filename.lower().endswith(".csv") or file_bytes.startswith(b"\"") or (b"," in file_bytes[:500] and not file_bytes.startswith(b"PK"))

    if is_csv:
        csv_rows = _parse_csv_rows(file_bytes)
        if len(csv_rows) <= 1:
            result.errors.append(ImportError("File", 0, "file", "CSV file contains no data rows"))
            return result
        data_rows = csv_rows[1:]
        return await _parse_flat_hierarchy_rows(data_rows, actual_state_id, db, result)

    try:
        wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as exc:
        result.errors.append(ImportError("File", 0, "file", f"Cannot read Excel file: {exc}"))
        return result

    # Check if multi-sheet workbook
    if "Regions" in wb.sheetnames or "Locations" in wb.sheetnames:
        return await _parse_multisheet_hierarchy(wb, actual_state_id, db, result)

    # Flat single sheet workbook
    ws = wb.active
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if any(v is not None and str(v).strip() for v in r):
            rows.append([_cell_str(list(r), idx) for idx in range(len(r))])
    return await _parse_flat_hierarchy_rows(rows, actual_state_id, db, result)


async def _parse_multisheet_hierarchy(wb, state_id: str, db: AsyncSession, result: HierarchyImportResult) -> HierarchyImportResult:
    region_rows = _read_sheet(wb, "Regions")
    region_name_map: dict[str, str] = {}
    existing_region_codes = {
        r[0]: r[1]
        for r in (await db.execute(
            select(Region.region_name, Region.region_code).where(Region.state_id == state_id)
        )).all()
    }

    for row_idx, row in enumerate(region_rows, start=3):
        region_name = _cell_str(row, 0)
        region_code = _cell_str(row, 1) or generate_region_code(region_name)
        regional_pastor = _cell_str(row, 2)
        region_head = _cell_str(row, 3)

        if not region_name:
            result.errors.append(ImportError("Regions", row_idx, "Region Name", "Region Name is required"))
            continue
        if not re.match(r"^[A-Za-z0-9]{2,6}$", region_code):
            result.errors.append(ImportError("Regions", row_idx, "Region Code", f"Code '{region_code}' must be 2-6 alphanumeric chars"))
            continue
        region_code = region_code.upper()

        if region_name in region_name_map:
            result.errors.append(ImportError("Regions", row_idx, "Region Name", f"Duplicate region '{region_name}' in file"))
            continue
        if region_name in existing_region_codes:
            result.errors.append(ImportError("Regions", row_idx, "Region Name", f"Region '{region_name}' already exists in this state"))
            continue

        region_name_map[region_name] = region_code
        result.regions.append({
            "region_name": region_name,
            "region_code": region_code,
            "regional_pastor": regional_pastor,
            "region_head": region_head,
            "state_id": state_id,
        })

    # Groups
    group_rows = _read_sheet(wb, "Groups")
    group_name_map: dict[str, str] = {}
    existing_groups_by_region: dict[str, set[str]] = {}
    for r in (await db.execute(select(Region.region_name, Region.region_id).where(Region.state_id == state_id))).all():
        groups = (await db.execute(select(Group.group_name).where(Group.region_id == r[1]))).scalars().all()
        existing_groups_by_region[r[0]] = set(groups)

    for row_idx, row in enumerate(group_rows, start=3):
        region_name = _cell_str(row, 0)
        group_name = _cell_str(row, 1)
        group_code = _cell_str(row, 2) or generate_group_code(group_name)
        group_pastor = _cell_str(row, 3)
        group_head = _cell_str(row, 4)

        if not region_name:
            result.errors.append(ImportError("Groups", row_idx, "Region Name", "Region Name is required"))
            continue
        if not group_name:
            result.errors.append(ImportError("Groups", row_idx, "Group Name", "Group Name is required"))
            continue
        if region_name not in region_name_map and region_name not in existing_region_codes:
            result.errors.append(ImportError("Groups", row_idx, "Region Name", f"Region '{region_name}' not found in Regions sheet or database"))
            continue
        if not re.match(r"^[A-Za-z0-9]{2,6}$", group_code):
            result.errors.append(ImportError("Groups", row_idx, "Group Code", f"Code '{group_code}' must be 2-6 alphanumeric chars"))
            continue
        group_code = group_code.upper()

        if group_name in group_name_map:
            result.errors.append(ImportError("Groups", row_idx, "Group Name", f"Duplicate group '{group_name}' in file"))
            continue
        if region_name in existing_groups_by_region and group_name in existing_groups_by_region[region_name]:
            result.errors.append(ImportError("Groups", row_idx, "Group Name", f"Group '{group_name}' already exists under '{region_name}'"))
            continue

        group_name_map[group_name] = group_code
        result.groups.append({
            "region_name": region_name,
            "group_name": group_name,
            "group_code": group_code,
            "group_pastor": group_pastor,
            "group_head": group_head,
        })

    # Locations
    loc_rows = _read_sheet(wb, "Locations")
    valid_church_types = {"DLBC", "DLCF", "DLSO"}

    for row_idx, row in enumerate(loc_rows, start=3):
        group_name = _cell_str(row, 0)
        loc_name = _cell_str(row, 1)
        church_type = _cell_str(row, 2).upper()
        address = _cell_str(row, 3)
        associate_cord = _cell_str(row, 4)
        pastor = _cell_str(row, 5)
        phone = _cell_str(row, 6)

        if not group_name:
            result.errors.append(ImportError("Locations", row_idx, "Group Name", "Group Name is required"))
            continue
        if not loc_name:
            result.errors.append(ImportError("Locations", row_idx, "Location Name", "Location Name is required"))
            continue
        if church_type not in valid_church_types:
            result.errors.append(ImportError("Locations", row_idx, "Church Type", f"Church type must be DLBC, DLCF, or DLSO (got '{church_type}')"))
            continue

        if group_name not in group_name_map:
            grp = (await db.execute(select(Group).where(Group.group_name == group_name))).scalars().first()
            if not grp:
                result.errors.append(ImportError("Locations", row_idx, "Group Name", f"Group '{group_name}' not found in Groups sheet or database"))
                continue

        result.locations.append({
            "group_name": group_name,
            "location_name": loc_name,
            "church_type": church_type,
            "address": address,
            "associate_cord": associate_cord,
            "pastor": pastor,
            "phone": phone,
        })

    return result


async def _parse_flat_hierarchy_rows(rows: list[list[str]], state_id: str, db: AsyncSession, result: HierarchyImportResult) -> HierarchyImportResult:
    """
    Parse flat hierarchy rows where each row contains Region, Group, and Location.
    Columns: [Region Name, Region Code, Group Name, Group Code, Location Name, Church Type, Address, Pastor, Phone]
    """
    seen_regions: dict[str, str] = {}
    seen_groups: dict[str, str] = {}
    valid_church_types = {"DLBC", "DLCF", "DLSO"}

    existing_regions = {
        r[0]: r[1]
        for r in (await db.execute(select(Region.region_name, Region.region_code).where(Region.state_id == state_id))).all()
    }

    for row_idx, row in enumerate(rows, start=2):
        if len(row) < 5:
            continue
        region_name = _cell_str(row, 0)
        region_code = _cell_str(row, 1) or generate_region_code(region_name)
        group_name = _cell_str(row, 2)
        group_code = _cell_str(row, 3) or generate_group_code(group_name)
        location_name = _cell_str(row, 4)
        church_type = (_cell_str(row, 5) or "DLCF").upper()
        address = _cell_str(row, 6)
        pastor = _cell_str(row, 7)
        phone = _cell_str(row, 8)

        if not region_name:
            result.errors.append(ImportError("Flat", row_idx, "Region Name", "Region Name is required"))
            continue
        if not group_name:
            result.errors.append(ImportError("Flat", row_idx, "Group Name", "Group Name is required"))
            continue
        if not location_name:
            result.errors.append(ImportError("Flat", row_idx, "Location Name", "Location Name is required"))
            continue
        if church_type not in valid_church_types:
            result.errors.append(ImportError("Flat", row_idx, "Church Type", f"Church Type must be DLBC, DLCF, or DLSO (got '{church_type}')"))
            continue

        region_code = region_code.upper()
        group_code = group_code.upper()

        if region_name not in seen_regions and region_name not in existing_regions:
            seen_regions[region_name] = region_code
            result.regions.append({
                "region_name": region_name,
                "region_code": region_code,
                "regional_pastor": None,
                "region_head": None,
                "state_id": state_id,
            })

        if group_name not in seen_groups:
            seen_groups[group_name] = group_code
            result.groups.append({
                "region_name": region_name,
                "group_name": group_name,
                "group_code": group_code,
                "group_pastor": None,
                "group_head": None,
            })

        result.locations.append({
            "group_name": group_name,
            "location_name": location_name,
            "church_type": church_type,
            "address": address,
            "associate_cord": None,
            "pastor": pastor,
            "phone": phone,
        })

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Workers validation
# ─────────────────────────────────────────────────────────────────────────────

async def parse_and_validate_workers(
    file_bytes: bytes,
    db: AsyncSession,
    filename: str = "",
) -> WorkersImportResult:
    result = WorkersImportResult()

    is_csv = filename.lower().endswith(".csv") or file_bytes.startswith(b"\"") or (b"," in file_bytes[:500] and not file_bytes.startswith(b"PK"))

    if is_csv:
        csv_rows = _parse_csv_rows(file_bytes)
        if len(csv_rows) <= 1:
            result.errors.append(ImportError("File", 0, "file", "CSV file contains no worker rows"))
            return result
        rows = csv_rows[1:]
    else:
        try:
            wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
            rows = _read_sheet(wb, "Workers")
            if not rows and wb.sheetnames:
                ws = wb.active
                rows = []
                for r in ws.iter_rows(min_row=3, values_only=True):
                    if any(v is not None and str(v).strip() for v in r):
                        rows.append(list(r))
        except Exception as exc:
            result.errors.append(ImportError("File", 0, "file", f"Cannot read file: {exc}"))
            return result

    if not rows:
        result.errors.append(ImportError("Workers", 0, "file", "No worker rows found"))
        return result

    loc_map_rows = (await db.execute(select(Location.location_name, Location.location_id, Location.church_type))).all()
    loc_map: dict[str, dict] = {r[0]: {"location_id": r[1], "church_type": r[2]} for r in loc_map_rows}

    seen_phones: set[str] = set()
    seen_emails: set[str] = set()

    existing_phones = set((await db.execute(select(Worker.phone))).scalars().all())
    existing_emails = set((await db.execute(select(Worker.email))).scalars().all())

    valid_genders = {"Male", "Female"}
    valid_marital = {"Single", "Married", "Widowed", ""}

    for row_idx, row in enumerate(rows, start=3):
        name = _cell_str(row, 0)
        gender = _cell_str(row, 1)
        phone = _cell_str(row, 2)
        email = _cell_str(row, 3).lower()
        loc_name = _cell_str(row, 4)
        unit = _cell_str(row, 5)
        address = _cell_str(row, 6)
        occupation = _cell_str(row, 7)
        marital_status = _cell_str(row, 8)

        errors_in_row = False

        if not name:
            result.errors.append(ImportError("Workers", row_idx, "Full Name", "Name is required"))
            errors_in_row = True
        if gender not in valid_genders:
            result.errors.append(ImportError("Workers", row_idx, "Gender", f"Must be Male or Female (got '{gender}')"))
            errors_in_row = True
        if not phone:
            result.errors.append(ImportError("Workers", row_idx, "Phone", "Phone is required"))
            errors_in_row = True
        elif phone in seen_phones:
            result.errors.append(ImportError("Workers", row_idx, "Phone", f"Duplicate phone '{phone}' in file"))
            errors_in_row = True
        elif phone in existing_phones:
            result.errors.append(ImportError("Workers", row_idx, "Phone", f"Phone '{phone}' already registered"))
            errors_in_row = True
        if not email:
            result.errors.append(ImportError("Workers", row_idx, "Email", "Email is required"))
            errors_in_row = True
        elif email in seen_emails:
            result.errors.append(ImportError("Workers", row_idx, "Email", f"Duplicate email '{email}' in file"))
            errors_in_row = True
        elif email in existing_emails:
            result.errors.append(ImportError("Workers", row_idx, "Email", f"Email '{email}' already registered"))
            errors_in_row = True
        if not loc_name:
            result.errors.append(ImportError("Workers", row_idx, "Location Name", "Location Name is required"))
            errors_in_row = True
        elif loc_name not in loc_map:
            result.errors.append(ImportError("Workers", row_idx, "Location Name", f"Location '{loc_name}' not found in system"))
            errors_in_row = True
        if not unit:
            result.errors.append(ImportError("Workers", row_idx, "Unit", "Unit is required"))
            errors_in_row = True
        if marital_status and marital_status.title() not in {v.title() for v in valid_marital if v}:
            result.errors.append(ImportError("Workers", row_idx, "Marital Status", f"Must be Single, Married, or Widowed"))
            errors_in_row = True

        if not errors_in_row:
            seen_phones.add(phone)
            seen_emails.add(email)
            loc_info = loc_map[loc_name]
            result.workers.append({
                "name": name,
                "gender": gender,
                "phone": phone,
                "email": email,
                "location_id": loc_info["location_id"],
                "location_name": loc_name,
                "church_type": loc_info["church_type"],
                "unit": unit,
                "address": address,
                "occupation": occupation,
                "marital_status": marital_status.title() if marital_status else None,
            })

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Commit operations
# ─────────────────────────────────────────────────────────────────────────────

async def commit_hierarchy(
    db: AsyncSession,
    result: HierarchyImportResult,
    state_id: str,
) -> dict[str, int]:
    """Atomically insert validated hierarchy rows into the database."""
    if not result.is_valid:
        raise ValueError("Import result has errors; cannot commit")

    state_row = await _resolve_state(db, state_id)
    if not state_row:
        raise ValueError(f"State {state_id} not found")

    actual_state_id = str(state_row.state_id)
    created = {"regions": 0, "groups": 0, "locations": 0}

    # Region lookup
    existing_regions = {
        r[0]: r[1]
        for r in (await db.execute(
            select(Region.region_name, Region.region_id).where(Region.state_id == actual_state_id)
        )).all()
    }
    region_id_map: dict[str, str] = {}
    region_path_map: dict[str, str] = {}

    for reg_data in result.regions:
        new_region = Region(
            state_id=actual_state_id,
            region_code=reg_data["region_code"],
            region_name=reg_data["region_name"],
            regional_pastor=reg_data.get("regional_pastor") or None,
            region_head=reg_data.get("region_head") or None,
            path=f"{state_row.path}.{reg_data['region_code']}",
        )
        db.add(new_region)
        await db.flush()
        await db.refresh(new_region)
        region_id_map[reg_data["region_name"]] = str(new_region.region_id)
        region_path_map[reg_data["region_name"]] = str(new_region.path)
        created["regions"] += 1

    for rname, rid in existing_regions.items():
        region_path = (await db.execute(select(Region.path).where(Region.region_id == rid))).scalar_one()
        region_id_map[rname] = str(rid)
        region_path_map[rname] = str(region_path)

    # Group lookup
    existing_groups: dict[str, dict] = {}
    for r in (await db.execute(select(Group.group_name, Group.group_id, Group.path))).all():
        existing_groups[r[0]] = {"group_id": str(r[1]), "path": str(r[2])}

    group_id_map: dict[str, str] = {}
    group_path_map: dict[str, str] = {}

    for grp_data in result.groups:
        rname = grp_data["region_name"]
        parent_id = region_id_map[rname]
        parent_path = region_path_map[rname]
        new_group = Group(
            region_id=parent_id,
            group_code=grp_data["group_code"],
            group_name=grp_data["group_name"],
            group_pastor=grp_data.get("group_pastor") or None,
            group_head=grp_data.get("group_head") or None,
            path=f"{parent_path}.{grp_data['group_code']}",
        )
        db.add(new_group)
        await db.flush()
        await db.refresh(new_group)
        group_id_map[grp_data["group_name"]] = str(new_group.group_id)
        group_path_map[grp_data["group_name"]] = str(new_group.path)
        created["groups"] += 1

    for gname, ginfo in existing_groups.items():
        group_id_map[gname] = ginfo["group_id"]
        group_path_map[gname] = ginfo["path"]

    # Locations
    for loc_data in result.locations:
        gname = loc_data["group_name"]
        parent_id = group_id_map[gname]
        parent_path = group_path_map[gname]
        loc_code = await next_location_code(db, parent_id)
        new_loc = Location(
            group_id=parent_id,
            location_code=loc_code,
            location_name=loc_data["location_name"],
            church_type=loc_data["church_type"],
            address=loc_data.get("address") or None,
            associate_cord=loc_data.get("associate_cord") or None,
            path=f"{parent_path}.{loc_code}",
        )
        db.add(new_loc)
        created["locations"] += 1

    await db.commit()
    return created


async def commit_workers(
    db: AsyncSession,
    result: WorkersImportResult,
    state_code: str,
) -> dict[str, int]:
    """Atomically insert validated worker rows."""
    if not result.is_valid:
        raise ValueError("Import result has errors; cannot commit")

    from app.models.core import generate_public_person_code

    created = {"workers": 0}
    loc_paths: dict[str, str] = {}

    for wdata in result.workers:
        lid = wdata["location_id"]
        if lid not in loc_paths:
            loc = (await db.execute(select(Location).where(Location.location_id == lid))).scalars().first()
            if loc:
                loc_paths[lid] = str(loc.path)

        region_n = "Unknown"
        group_n = "Unknown"
        state_name = state_code
        loc = (await db.execute(select(Location).where(Location.location_id == lid))).scalars().first()
        if loc:
            grp = (await db.execute(select(Group).where(Group.group_id == loc.group_id))).scalars().first()
            if grp:
                group_n = grp.group_name
                reg = (await db.execute(select(Region).where(Region.region_id == grp.region_id))).scalars().first()
                if reg:
                    region_n = reg.region_name
                    st = (await db.execute(select(State).where(State.state_id == reg.state_id))).scalars().first()
                    if st:
                        state_name = st.state_name

        base_code = generate_public_person_code(state_code, wdata["phone"])
        generated_user_id = None
        for idx in range(1, 100):
            candidate = base_code if idx == 1 else f"{base_code}{idx:02d}"
            exists = (await db.execute(select(Worker.user_id == candidate))).scalars().first()
            if not exists:
                generated_user_id = candidate
                break

        new_worker = Worker(
            location_id=lid,
            location_name=wdata["location_name"],
            church_type=wdata["church_type"],
            state=state_name,
            region=region_n,
            group=group_n,
            name=wdata["name"],
            gender=wdata["gender"],
            phone=wdata["phone"],
            email=wdata["email"],
            address=wdata.get("address") or None,
            occupation=wdata.get("occupation") or None,
            marital_status=wdata.get("marital_status") or None,
            unit=wdata["unit"],
            status="Active",
            approval_status="approved",
            user_id=generated_user_id or base_code,
            path=loc_paths.get(lid, ""),
        )
        db.add(new_worker)
        created["workers"] += 1

    await db.commit()
    return created
