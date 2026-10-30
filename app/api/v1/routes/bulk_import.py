"""
Bulk Import / Export API routes.

Endpoints:
  GET  /bulk/templates/hierarchy   - Download blank hierarchy Excel template
  GET  /bulk/templates/workers     - Download blank workers Excel template
  POST /bulk/hierarchy/validate    - Parse & dry-run validate a hierarchy file (xlsx or csv)
  POST /bulk/hierarchy/commit      - Atomically insert validated hierarchy
  POST /bulk/workers/validate      - Parse & dry-run validate a workers file (xlsx or csv)
  POST /bulk/workers/commit        - Atomically insert validated workers
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.services.bulk_import_service import (
    commit_hierarchy,
    commit_workers,
    generate_hierarchy_template,
    generate_workers_template,
    parse_and_validate_hierarchy,
    parse_and_validate_workers,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Template downloads
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/templates/hierarchy",
    response_class=Response,
    summary="Download blank hierarchy Excel template",
)
async def download_hierarchy_template(
    current_user: User = Depends(deps.get_current_active_user),
) -> Response:
    """Download a pre-formatted .xlsx template for bulk hierarchy import."""
    xlsx_bytes = generate_hierarchy_template()
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=DCL_Hierarchy_Import_Template.xlsx"},
    )


@router.get(
    "/templates/workers",
    response_class=Response,
    summary="Download blank workers Excel template",
)
async def download_workers_template(
    current_user: User = Depends(deps.get_current_active_user),
) -> Response:
    """Download a pre-formatted .xlsx template for bulk workers import."""
    xlsx_bytes = generate_workers_template()
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=DCL_Workers_Import_Template.xlsx"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Hierarchy import
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/hierarchy/validate",
    summary="Validate a hierarchy import file (dry-run)",
    dependencies=[Depends(deps.PermissionChecker("hierarchy:create_location"))],
)
async def validate_hierarchy_import(
    file: UploadFile = File(..., description="Hierarchy Excel or CSV file"),
    state_id: str = Form(..., description="UUID of the state to import under"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Dry-run parse and validate a hierarchy import file.

    Returns a summary of discovered rows and any validation errors.
    Does NOT write to the database.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    result = await parse_and_validate_hierarchy(content, state_id, db, filename=file.filename or "")
    return {
        "valid": result.is_valid,
        "summary": result.summary,
        "errors": [
            {
                "sheet": e.sheet,
                "row": e.row,
                "column": e.column,
                "message": e.message,
            }
            for e in result.errors
        ],
        "preview": {
            "regions": [r["region_name"] for r in result.regions[:10]],
            "groups": [g["group_name"] for g in result.groups[:10]],
            "locations": [loc["location_name"] for loc in result.locations[:10]],
        },
    }


@router.post(
    "/hierarchy/commit",
    summary="Commit a validated hierarchy import file",
    dependencies=[Depends(deps.PermissionChecker("hierarchy:create_location"))],
)
async def commit_hierarchy_import(
    file: UploadFile = File(..., description="Hierarchy Excel or CSV file"),
    state_id: str = Form(..., description="UUID of the state to import under"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Parse, validate and commit a hierarchy import file atomically.

    Returns counts of created records, or a 422 with errors if validation fails.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    result = await parse_and_validate_hierarchy(content, state_id, db, filename=file.filename or "")
    if not result.is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Validation failed — no records were saved",
                "errors": [
                    {"sheet": e.sheet, "row": e.row, "column": e.column, "message": e.message}
                    for e in result.errors
                ],
            },
        )

    try:
        counts = await commit_hierarchy(db, result, state_id)
    except Exception as exc:
        logger.error("Hierarchy commit failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Commit failed: {exc}")

    return {
        "status": "success",
        "created": counts,
        "message": (
            f"Imported {counts['regions']} region(s), "
            f"{counts['groups']} group(s), "
            f"{counts['locations']} location(s)."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Workers import
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/workers/validate",
    summary="Validate a workers import file (dry-run)",
    dependencies=[Depends(deps.PermissionChecker("workers:create"))],
)
async def validate_workers_import(
    file: UploadFile = File(..., description="Workers Excel or CSV file"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Dry-run parse and validate a workers import file.

    Returns a summary of discovered rows and any validation errors.
    Does NOT write to the database.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    result = await parse_and_validate_workers(content, db, filename=file.filename or "")
    return {
        "valid": result.is_valid,
        "summary": result.summary,
        "errors": [
            {
                "sheet": e.sheet,
                "row": e.row,
                "column": e.column,
                "message": e.message,
            }
            for e in result.errors
        ],
        "preview": [w["name"] for w in result.workers[:10]],
    }


@router.post(
    "/workers/commit",
    summary="Commit a validated workers import file",
    dependencies=[Depends(deps.PermissionChecker("workers:create"))],
)
async def commit_workers_import(
    file: UploadFile = File(..., description="Workers Excel or CSV file"),
    state_code: str = Form("KW", description="2-3 letter state code for ID generation (e.g. KW)"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Parse, validate and commit a workers import file atomically.

    Returns count of created workers, or a 422 with errors if validation fails.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    result = await parse_and_validate_workers(content, db, filename=file.filename or "")
    if not result.is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Validation failed — no records were saved",
                "errors": [
                    {"sheet": e.sheet, "row": e.row, "column": e.column, "message": e.message}
                    for e in result.errors
                ],
            },
        )

    try:
        counts = await commit_workers(db, result, state_code.upper())
    except Exception as exc:
        logger.error("Workers commit failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Commit failed: {exc}")

    return {
        "status": "success",
        "created": counts,
        "message": f"Successfully imported {counts['workers']} worker(s).",
    }
