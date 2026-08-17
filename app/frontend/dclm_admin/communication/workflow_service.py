from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from ..backend import BackendClientError
from ..backend.config import get_backend_config
from ..mock_data import STORE
from .api_client import get_api_client
from .async_compat import async_client, dual_mode_class, maybe_await
from .auth_service import AuthService
from .people_service import PeopleService
from .request_cache import request_cached


LEVEL_STAGE_MAP = {
    4: "Group review",
    5: "Region review",
    6: "State review",
    7: "National review",
}


def _safe_date(value: Any) -> str:
    raw = str(value or "")
    return raw.replace("T", " ")[:16] if raw else "Not recorded"


def _request_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("submitted_at") or ""), str(row.get("worker_name") or ""))


def _request_token(kind: str, record_id: str) -> str:
    return f"{kind}--{record_id}"


def _parse_request_token(token: str) -> tuple[str, str]:
    if "--" not in token:
        raise BackendClientError("Unknown workflow item identifier.")
    kind, record_id = token.split("--", 1)
    return kind, record_id


async def _worker_maps(request, ctx) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    workers = await PeopleService.list_workers(request, ctx)
    users = await PeopleService.list_users(request, ctx)
    return (
        {row["worker_id"]: row for row in workers},
        {row.get("worker_id", ""): row for row in users if row.get("worker_id")},
    )


def _requested_by_label(requested_by: str, identity) -> str:
    if identity and requested_by == identity.user_id:
        return identity.display_name
    return requested_by or "Unknown requester"


def _normalize_transfer(row: dict[str, Any], worker: dict[str, Any] | None, identity) -> dict[str, Any]:
    request_id = str(row.get("id") or "")
    status = str(row.get("status") or "pending")
    return {
        "request_id": _request_token("transfer_request", request_id),
        "backend_kind": "transfer_request",
        "backend_id": request_id,
        "worker_id": str(row.get("worker_id") or ""),
        "worker_name": worker["name"] if worker else "Unknown worker",
        "request_type": "transfer_request",
        "status": status,
        "current_stage": "Awaiting transfer review" if status == "pending" else "Transfer approved" if status == "approved" else "Transfer rejected",
        "origin_location": worker["location"] if worker else str(row.get("from_location_id") or "-"),
        "destination_location": str(row.get("to_location_id") or "-"),
        "requested_by": _requested_by_label(str(row.get("requested_by") or ""), identity),
        "submitted_at": _safe_date(row.get("created_at")),
        "summary": str(row.get("reason") or "Transfer request waiting for review."),
        "timeline": [
            {"label": "Submitted", "state": "done", "note": "Transfer request created."},
            {"label": "Review", "state": "current" if status == "pending" else "done", "note": "Awaiting decision."},
            {"label": "Final decision", "state": "pending" if status == "pending" else "done", "note": status.replace("_", " ").title()},
        ],
        "review_history": (
            [
                {
                    "reviewer": str(row.get("approved_by") or "Reviewer"),
                    "action": "approve",
                    "note": "Transfer approved.",
                    "time": _safe_date(row.get("approved_at")),
                }
            ]
            if row.get("approved_by")
            else []
        ),
        "path": worker.get("path") if worker else "",
        "allow_escalate": False,
    }


def _normalize_status_change(row: dict[str, Any], worker: dict[str, Any] | None, identity) -> dict[str, Any]:
    request_id = str(row.get("id") or "")
    status = str(row.get("status") or "pending")
    old_status = str(row.get("old_status") or (worker["status"] if worker else "Unknown"))
    new_status = str(row.get("new_status") or "")
    return {
        "request_id": _request_token("status_change", request_id),
        "backend_kind": "status_change",
        "backend_id": request_id,
        "worker_id": str(row.get("worker_id") or ""),
        "worker_name": worker["name"] if worker else "Unknown worker",
        "request_type": "status_change",
        "status": status,
        "current_stage": "Awaiting status review" if status == "pending" else "Status approved" if status == "approved" else "Status rejected",
        "origin_location": worker["location"] if worker else "-",
        "destination_location": "-",
        "requested_by": _requested_by_label(str(row.get("requested_by") or ""), identity),
        "submitted_at": _safe_date(row.get("created_at")),
        "summary": str(row.get("reason") or f"Change worker status from {old_status} to {new_status}."),
        "timeline": [
            {"label": "Submitted", "state": "done", "note": "Status change request created."},
            {"label": "Review", "state": "current" if status == "pending" else "done", "note": "Awaiting decision."},
            {"label": "Final decision", "state": "pending" if status == "pending" else "done", "note": status.replace("_", " ").title()},
        ],
        "review_history": (
            [
                {
                    "reviewer": str(row.get("approved_by") or "Reviewer"),
                    "action": "approve",
                    "note": f"Status changed to {new_status}.",
                    "time": _safe_date(row.get("approved_at")),
                }
            ]
            if row.get("approved_by")
            else []
        ),
        "path": worker.get("path") if worker else "",
        "allow_escalate": False,
    }


def _normalize_removal(row: dict[str, Any], worker: dict[str, Any] | None, identity) -> dict[str, Any]:
    request_id = str(row.get("id") or "")
    status = str(row.get("status") or "pending")
    current_level = int(row.get("current_level") or 4)
    reviews = row.get("reviews") or []
    history = [
        {
            "reviewer": str(entry.get("reviewer_id") or f"Level {entry.get('level') or current_level} reviewer"),
            "action": str(entry.get("action") or "review"),
            "note": str(entry.get("notes") or ""),
            "time": _safe_date(entry.get("at")),
        }
        for entry in reviews
    ]
    timeline = [
        {"label": "Submitted", "state": "done", "note": "Removal request created."},
        {
            "label": LEVEL_STAGE_MAP.get(current_level, f"Level {current_level} review"),
            "state": "current" if status in {"pending", "escalated"} else "done",
            "note": "Waiting for the current governance level to decide.",
        },
        {
            "label": "Final decision",
            "state": "pending" if status in {"pending", "escalated"} else "done",
            "note": status.replace("_", " ").title(),
        },
    ]
    return {
        "request_id": _request_token("removal_request", request_id),
        "backend_kind": "removal_request",
        "backend_id": request_id,
        "worker_id": str(row.get("worker_id") or ""),
        "worker_name": worker["name"] if worker else "Unknown worker",
        "request_type": "removal_request",
        "status": status,
        "current_stage": LEVEL_STAGE_MAP.get(current_level, f"Level {current_level} review"),
        "origin_location": worker["location"] if worker else "-",
        "destination_location": "-",
        "requested_by": _requested_by_label(str(row.get("requested_by") or ""), identity),
        "submitted_at": _safe_date(row.get("created_at")),
        "summary": str(row.get("reason") or "Worker removal request awaiting review."),
        "timeline": timeline,
        "review_history": history,
        "path": worker.get("path") if worker else "",
        "allow_escalate": True,
    }


class WorkflowService:
    @staticmethod
    async def live_enabled(request) -> bool:
        return bool(AuthService.get_access_token(request))

    @staticmethod
    async def use_mock(request) -> bool:
        if AuthService.get_access_token(request):
            return False
        if get_backend_config().enabled:
            raise BackendClientError("Backend session required for workflows.")
        return True

    @staticmethod
    async def list_transfer_requests(request, ctx, *, request_type: str = "all", status: str = "all", mine_only: bool = False, review_only: bool = False) -> list[dict[str, Any]]:
        if await WorkflowService.use_mock(request):
            return STORE.list_requests(
                ctx.current_scope_path,
                request_type=request_type,
                status=status,
                requester=ctx.profile.user_name,
                mine_only=mine_only,
                review_only=review_only,
            )
        scope_path = await PeopleService.effective_scope_path(request, ctx)
        identity = AuthService.get_identity(request)

        async def load_rows() -> list[dict[str, Any]]:
            client = async_client(get_api_client())
            access_token = AuthService.get_access_token(request)
            worker_map, _user_by_worker = await maybe_await(_worker_maps(request, ctx))
            rows: list[dict[str, Any]] = []
            loaders: list[tuple[str, Any]] = []

            if request_type in {"all", "transfer_request"}:
                loaders.append(("transfer_request", client.list_transfer_requests(access_token, status=None if status == "all" else status)))
            if request_type in {"all", "status_change"}:
                loaders.append(("status_change", client.list_status_change_requests(access_token, status=None if status == "all" else status)))
            if request_type in {"all", "removal_request"}:
                loaders.append(("removal_request", client.list_removal_requests(access_token, status=None if status == "all" else status)))

            loaded = await asyncio.gather(*(maybe_await(loader) for _name, loader in loaders)) if loaders else []
            for (name, _loader), loaded_rows in zip(loaders, loaded):
                if name == "transfer_request":
                    for row in loaded_rows:
                        worker = worker_map.get(str(row.get("worker_id") or ""))
                        rows.append(_normalize_transfer(row, worker, identity))
                elif name == "status_change":
                    for row in loaded_rows:
                        worker = worker_map.get(str(row.get("worker_id") or ""))
                        rows.append(_normalize_status_change(row, worker, identity))
                elif name == "removal_request":
                    for row in loaded_rows:
                        worker = worker_map.get(str(row.get("worker_id") or ""))
                        rows.append(_normalize_removal(row, worker, identity))
            return rows

        rows = await request_cached(
            request,
            ("workflow", "requests", scope_path, request_type, status, mine_only, review_only),
            load_rows,
        )

        if mine_only and identity:
            rows = [row for row in rows if row["requested_by"] == identity.display_name or str(row.get("requested_by")) == identity.user_id]
        if review_only and mine_only:
            rows = []
        if status != "all":
            rows = [row for row in rows if row["status"] == status]
        return sorted(rows, key=_request_sort_key, reverse=True)

    @staticmethod
    async def list_status_change_requests(request, ctx, request_token: str) -> dict[str, Any] | None:
        if await WorkflowService.use_mock(request):
            return STORE.get_request(request_token)
        rows = await WorkflowService.list_requests(request, ctx, request_type="all", status="all")
        return next((row for row in rows if row["request_id"] == request_token), None)

    @staticmethod
    async def list_removal_requests(request, ctx, request_token: str, action: str, notes: str) -> dict[str, Any] | None:
        if await WorkflowService.use_mock(request):
            return STORE.act_request(request_token, action, notes, ctx.profile.user_name)
        kind, backend_id = _parse_request_token(request_token)
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        if kind == "transfer_request":
            if action == "approve":
                await client.approve_transfer_request(access_token, backend_id)
            elif action == "reject":
                await client.reject_transfer_request(access_token, backend_id, notes or None)
            else:
                raise BackendClientError("Transfer requests cannot be escalated from this review flow.")
        elif kind == "status_change":
            if action == "approve":
                await client.approve_status_change_request(access_token, backend_id)
            elif action == "reject":
                await client.reject_status_change_request(access_token, backend_id, notes or None)
            else:
                raise BackendClientError("Status change requests cannot be escalated from this review flow.")
        elif kind == "removal_request":
            if action == "approve":
                await client.approve_removal_request(access_token, backend_id, notes or None)
            elif action == "reject":
                await client.reject_removal_request(access_token, backend_id, notes or None)
            elif action == "escalate":
                await client.escalate_removal_request(access_token, backend_id, notes.strip())
            else:
                raise BackendClientError("Unknown workflow action.")
        else:
            raise BackendClientError("Unknown workflow request type.")
        return await WorkflowService.get_request(request, ctx, request_token)

    @staticmethod
    async def approve_transfer_request(request, ctx, *, kind: str = "all") -> list[dict[str, Any]]:
        if await WorkflowService.use_mock(request):
            return STORE.list_inbox(ctx.current_scope_path, kind=kind)
        scope_path = await PeopleService.effective_scope_path(request, ctx)

        async def load_items() -> list[dict[str, Any]]:
            client = async_client(get_api_client())
            access_token = AuthService.get_access_token(request)
            items: list[dict[str, Any]] = []
            request_rows: list[dict[str, Any]] = []
            pending_worker_rows: list[dict[str, Any]] = []
            pending_user_rows: list[dict[str, Any]] = []

            loaders: list[tuple[str, Any]] = []
            if kind in {"all", "transfer_request", "status_change", "removal_request"}:
                loaders.append(
                    (
                        "workflow",
                        WorkflowService.list_requests(request, ctx, request_type="all", status="all", review_only=True),
                    )
                )
            if kind in {"all", "worker_registration"}:
                loaders.append(("workers", client.list_pending_workers(access_token, scope_path=scope_path)))
            if kind in {"all", "user_approval"}:
                loaders.append(("users", client.list_pending_users(access_token)))

            if loaders:
                loaded = await asyncio.gather(*(maybe_await(loader) for _name, loader in loaders))
                for (name, _loader), rows in zip(loaders, loaded):
                    if name == "workflow":
                        request_rows = rows
                    elif name == "workers":
                        pending_worker_rows = rows
                    elif name == "users":
                        pending_user_rows = rows

            if kind in {"all", "worker_registration"}:
                worker_ids = [str(row.get("worker_id") or "") for row in pending_worker_rows]
                workers = await asyncio.gather(*(maybe_await(PeopleService.get_worker(request, worker_id)) for worker_id in worker_ids))
                for row, worker in zip(pending_worker_rows, workers):
                    if worker is None:
                        continue
                    items.append(
                        {
                            "item_id": _request_token("worker_registration", worker["worker_id"]),
                            "subject": worker["name"],
                            "title": "Worker registration pending approval",
                            "priority": "medium",
                            "location": worker["location"],
                            "submitted_at": worker["added_date"] or "Pending",
                            "summary": f"{worker['name']} is waiting for worker verification in {worker['location']}.",
                            "current_stage": "Worker verification",
                        }
                    )

            if kind in {"all", "user_approval"}:
                user_ids = [str(row.get("user_id") or "") for row in pending_user_rows]
                accounts = await asyncio.gather(*(maybe_await(PeopleService.get_user(request, user_id)) for user_id in user_ids))
                for row, account in zip(pending_user_rows, accounts):
                    if account is None:
                        continue
                    items.append(
                        {
                            "item_id": _request_token("user_approval", account["account_id"]),
                            "subject": account["name"],
                            "title": "User access request pending approval",
                            "priority": "medium",
                            "location": account["location"],
                            "submitted_at": _safe_date(row.get("created_at")),
                            "summary": f"{account['name']} is waiting for app access approval.",
                            "current_stage": "Account approval",
                        }
                    )

            for row in request_rows:
                if kind not in {"all", row["request_type"]}:
                    continue
                if row["status"] not in {"pending", "escalated"}:
                    continue
                items.append(
                    {
                        "item_id": _request_token("workflow", row["request_id"]),
                        "subject": row["worker_name"],
                        "title": row["request_type"].replace("_", " ").title(),
                        "priority": "high" if row["request_type"] == "removal_request" else "medium",
                        "location": row["origin_location"],
                        "submitted_at": row["submitted_at"],
                        "summary": row["summary"],
                        "current_stage": row["current_stage"],
                    }
                )
            return sorted(items, key=lambda row: row["submitted_at"], reverse=True)

        return await request_cached(request, ("workflow", "inbox", scope_path, kind), load_items)

    @staticmethod
    async def reject_transfer_request(request, ctx) -> int:
        if await WorkflowService.use_mock(request):
            return len(STORE.list_inbox(ctx.current_scope_path, kind="all"))

        scope_path = await PeopleService.effective_scope_path(request, ctx)

        async def load_count() -> int:
            client = async_client(get_api_client())
            access_token = AuthService.get_access_token(request)
            workflow_requests, pending_worker_rows, pending_user_rows = await asyncio.gather(
                maybe_await(WorkflowService.list_requests(request, ctx, request_type="all", status="all", review_only=True)),
                maybe_await(client.list_pending_workers(access_token, scope_path=scope_path)),
                maybe_await(client.list_pending_users(access_token)),
            )
            pending_workflows = sum(1 for row in workflow_requests if row["status"] in {"pending", "escalated"})
            pending_workers = len(pending_worker_rows)
            pending_users = len(pending_user_rows)
            return pending_workflows + pending_workers + pending_users

        return await request_cached(request, ("workflow", "pending-item-count", scope_path), load_count)

    @staticmethod
    async def approve_status_change_request(request, ctx, item_id: str) -> dict[str, Any] | None:
        if await WorkflowService.use_mock(request):
            return STORE.resolve_inbox_item(item_id)
        kind, record_id = _parse_request_token(item_id)
        if kind == "workflow":
            request_row = await WorkflowService.get_request(request, ctx, record_id)
            if request_row is None:
                return None
            worker = await PeopleService.get_worker(request, request_row["worker_id"])
            account = await PeopleService.get_user_by_worker(request, ctx, request_row["worker_id"])
            item = next((row for row in await WorkflowService.list_inbox(request, ctx) if row["item_id"] == item_id), None)
            return {"item": item or {}, "worker": worker, "account": account, "request": request_row}
        if kind == "worker_registration":
            worker = await PeopleService.get_worker(request, record_id)
            if worker is None:
                return None
            item = next((row for row in await WorkflowService.list_inbox(request, ctx, kind="worker_registration") if row["item_id"] == item_id), None)
            return {"item": item or {}, "worker": worker, "account": await PeopleService.get_user_by_worker(request, ctx, record_id), "request": None}
        if kind == "user_approval":
            account = await PeopleService.get_user(request, record_id)
            if account is None:
                return None
            worker = await PeopleService.get_worker(request, account["worker_id"]) if account.get("worker_id") else None
            item = next((row for row in await WorkflowService.list_inbox(request, ctx, kind="user_approval") if row["item_id"] == item_id), None)
            return {"item": item or {}, "worker": worker, "account": account, "request": None}
        return None

    @staticmethod
    async def reject_status_change_request(request, ctx, *, request_type: str, worker_id: str, reason: str, destination_location_id: str = "", new_status: str = "") -> dict[str, Any] | None:
        if await WorkflowService.use_mock(request):
            raise BackendClientError("Live request creation is only available in backend mode.")
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        if request_type == "transfer_request":
            created = await client.create_transfer_request(
                access_token,
                {"worker_id": worker_id, "to_location_id": destination_location_id, "reason": reason or None},
            )
            worker_map, _user_by_worker = await maybe_await(_worker_maps(request, ctx))
            return _normalize_transfer(created, worker_map.get(worker_id), AuthService.get_identity(request))
        if request_type == "status_change":
            created = await client.create_status_change_request(
                access_token,
                {"worker_id": worker_id, "new_status": new_status, "reason": reason or None},
            )
            worker_map, _user_by_worker = await maybe_await(_worker_maps(request, ctx))
            return _normalize_status_change(created, worker_map.get(worker_id), AuthService.get_identity(request))
        if request_type == "removal_request":
            created = await client.create_removal_request(
                access_token,
                {"worker_id": worker_id, "reason": reason},
            )
            worker_map, _user_by_worker = await maybe_await(_worker_maps(request, ctx))
            return _normalize_removal(created, worker_map.get(worker_id), AuthService.get_identity(request))
        raise BackendClientError("Unknown workflow request type.")

    @staticmethod
    async def approve_removal_request(request, ctx, item_id: str, action: str, notes: str) -> dict[str, Any] | None:
        if not await WorkflowService.live_enabled(request):
            return STORE.act_inbox_item(item_id, action, notes, actor_name=ctx.profile.user_name)
        kind, record_id = _parse_request_token(item_id)
        client = async_client(get_api_client())
        access_token = AuthService.get_access_token(request)
        if kind == "workflow":
            await WorkflowService.act_request(request, ctx, record_id, action, notes)
            return next((row for row in await WorkflowService.list_inbox(request, ctx) if row["item_id"] == item_id), None)
        if kind == "worker_registration":
            if action == "approve":
                await client.approve_worker(access_token, record_id)
            elif action == "reject":
                await client.reject_worker(access_token, record_id, notes or "Rejected from admin inbox.")
            else:
                raise BackendClientError("Worker registrations cannot be escalated from the inbox.")
            return next((row for row in await WorkflowService.list_inbox(request, ctx, kind="worker_registration") if row["item_id"] == item_id), None)
        if kind == "user_approval":
            if action == "approve":
                await client.approve_user(access_token, record_id)
            elif action == "reject":
                await client.reject_user(access_token, record_id, notes or "Rejected from admin inbox.")
            else:
                raise BackendClientError("User approvals cannot be escalated from the inbox.")
            return next((row for row in await WorkflowService.list_inbox(request, ctx, kind="user_approval") if row["item_id"] == item_id), None)
        raise BackendClientError("Unknown inbox item type.")

async def _create_workflow_request_public(
    request,
    ctx,
    *,
    request_type: str,
    worker_id: str,
    reason: str,
    destination_location_id: str = "",
    new_status: str = "",
) -> dict[str, Any] | None:
    if await WorkflowService.use_mock(request):
        raise BackendClientError("Live request creation is only available in backend mode.")
    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)
    if request_type == "transfer_request":
        created = await client.create_transfer_request(
            access_token,
            {"worker_id": worker_id, "to_location_id": destination_location_id, "reason": reason or None},
        )
        worker_map, _user_by_worker = await maybe_await(_worker_maps(request, ctx))
        return _normalize_transfer(created, worker_map.get(worker_id), AuthService.get_identity(request))
    if request_type == "status_change":
        created = await client.create_status_change_request(
            access_token,
            {"worker_id": worker_id, "new_status": new_status, "reason": reason or None},
        )
        worker_map, _user_by_worker = await maybe_await(_worker_maps(request, ctx))
        return _normalize_status_change(created, worker_map.get(worker_id), AuthService.get_identity(request))
    if request_type == "removal_request":
        created = await client.create_removal_request(access_token, {"worker_id": worker_id, "reason": reason})
        worker_map, _user_by_worker = await maybe_await(_worker_maps(request, ctx))
        return _normalize_removal(created, worker_map.get(worker_id), AuthService.get_identity(request))
    raise BackendClientError("Unknown workflow request type.")


WorkflowService.create_request = staticmethod(_create_workflow_request_public)
WorkflowService.list_requests = staticmethod(WorkflowService.list_transfer_requests)
WorkflowService.get_request = staticmethod(WorkflowService.list_status_change_requests)
WorkflowService.act_request = staticmethod(WorkflowService.list_removal_requests)
WorkflowService.list_inbox = staticmethod(WorkflowService.approve_transfer_request)
WorkflowService.pending_item_count = staticmethod(WorkflowService.reject_transfer_request)
WorkflowService.resolve_inbox_item = staticmethod(WorkflowService.approve_status_change_request)
WorkflowService.act_inbox_item = staticmethod(WorkflowService.approve_removal_request)

dual_mode_class(WorkflowService)

__all__ = ["WorkflowService"]
