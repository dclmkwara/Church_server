from datetime import datetime, timezone
from typing import List, Dict, Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.filters import scope_filter as _scope_filter
from app.models.approvals import WorkerRemovalRequest
from app.models.audit import NotificationReadState
from app.models.counts import Count
from app.models.fellowship_activities import FellowshipAttendance, PrayerRequest, Testimony
from app.models.offerings import Offering
from app.models.user import User, Worker


class NotificationService:
    @staticmethod
    async def poll_new_data(
        db: AsyncSession,
        scope_path: str,
        since: datetime,
        *,
        per_bucket_limit: int = 100,
    ) -> Dict[str, List[Any]]:
        """
        Check for new records in 8 tables since `since` timestamp.

        Queries are intentionally sequential because one AsyncSession cannot run
        concurrent operations safely. Each bucket is capped to avoid unbounded
        memory growth on long polling windows.
        """
        def _stmt(model, extra_filters=None):
            f = [_scope_filter(model.path, scope_path), model.created_at > since]
            if extra_filters:
                f.extend(extra_filters)
            return (
                select(model)
                .where(and_(*f))
                .order_by(model.created_at.desc())
                .limit(per_bucket_limit)
            )

        removal_stmt = select(WorkerRemovalRequest).where(and_(
            _scope_filter(WorkerRemovalRequest.path, scope_path),
            WorkerRemovalRequest.status.in_(["pending", "escalated"]),
            (WorkerRemovalRequest.created_at > since) | (WorkerRemovalRequest.escalated_at > since),
        )).order_by(WorkerRemovalRequest.created_at.desc()).limit(per_bucket_limit)

        counts_r = await db.execute(_stmt(Count))
        offerings_r = await db.execute(_stmt(Offering))
        attendance_r = await db.execute(_stmt(FellowshipAttendance))
        prayer_r = await db.execute(_stmt(PrayerRequest))
        workers_r = await db.execute(_stmt(Worker, [Worker.approval_status == "pending_verification"]))
        users_r = await db.execute(_stmt(User, [User.approval_status == "pending"]))
        removals_r = await db.execute(removal_stmt)
        testimonies_r = await db.execute(_stmt(Testimony))

        results: Dict[str, List[Any]] = {}

        counts = counts_r.scalars().all()
        if counts:
            results["counts"] = [{"id": str(c.id), "event_id": str(c.event_id) if c.event_id else None,
                                   "date": c.date, "created_at": c.created_at} for c in counts]

        offerings = offerings_r.scalars().all()
        if offerings:
            results["offerings"] = [{"id": str(o.id), "amount": str(o.amount),
                                     "event_id": str(o.event_id) if o.event_id else None,
                                     "created_at": o.created_at} for o in offerings]

        attendance = attendance_r.scalars().all()
        if attendance:
            results["fellowship_attendance"] = [{"id": str(a.id), "fellowship_id": a.fellowship_id,
                                                  "total": a.total, "created_at": a.created_at} for a in attendance]

        prayer_requests = prayer_r.scalars().all()
        if prayer_requests:
            results["prayer_requests"] = [{"id": str(p.id), "requestor": p.requestor_name,
                                           "created_at": p.created_at} for p in prayer_requests]

        workers = workers_r.scalars().all()
        if workers:
            results["pending_workers"] = [{"id": str(w.worker_id), "name": w.name,
                                           "created_at": w.created_at} for w in workers]

        users = users_r.scalars().all()
        if users:
            results["pending_users"] = [{"id": str(u.user_id), "name": u.name,
                                         "created_at": u.created_at} for u in users]

        removals = removals_r.scalars().all()
        if removals:
            results["worker_removals"] = [{"id": str(r.id), "worker_id": str(r.worker_id),
                                           "level": r.current_level, "status": r.status,
                                           "created_at": r.escalated_at or r.created_at} for r in removals]

        testimonies = testimonies_r.scalars().all()
        if testimonies:
            results["testimonies"] = [{"id": str(t.id), "title": t.title,
                                       "created_at": t.created_at} for t in testimonies]

        return results

    @staticmethod
    def _priority_for_kind(kind: str) -> str:
        if kind in {"pending_users", "pending_workers", "worker_removals"}:
            return "high"
        if kind in {"prayer_requests", "testimonies"}:
            return "medium"
        return "low"

    @staticmethod
    def _title_for_kind(kind: str) -> str:
        mapping = {
            "counts": "New count submitted",
            "offerings": "New offering submitted",
            "fellowship_attendance": "New fellowship attendance recorded",
            "prayer_requests": "New prayer request received",
            "pending_workers": "Worker registration awaiting review",
            "pending_users": "App access request awaiting review",
            "worker_removals": "Worker removal request awaiting governance review",
            "testimonies": "New testimony submitted",
        }
        return mapping.get(kind, kind.replace("_", " ").title())

    @staticmethod
    def _body_for_kind(kind: str, row: dict[str, Any]) -> str:
        if kind == "counts":
            return f"Count record {row.get('id') or ''} was submitted for review."
        if kind == "offerings":
            return f"Offering of {row.get('amount') or '0'} was submitted into the finance flow."
        if kind == "fellowship_attendance":
            return f"Fellowship attendance total: {row.get('total') or 0}."
        if kind == "prayer_requests":
            return f"{row.get('requestor') or 'A visitor'} submitted a prayer request."
        if kind == "pending_workers":
            return f"{row.get('name') or 'A worker'} is waiting for registration approval."
        if kind == "pending_users":
            return f"{row.get('name') or 'A user'} is waiting for app access approval."
        if kind == "worker_removals":
            return f"Removal request is at level {row.get('level') or '?'} with status {row.get('status') or 'pending'}."
        if kind == "testimonies":
            return f"Testimony '{row.get('title') or 'Untitled'}' was submitted."
        return "A new notification item was received."

    @staticmethod
    def _notification_key(kind: str, source_id: str) -> str:
        return f"{kind}:{source_id}"

    @staticmethod
    async def _read_state_map(db: AsyncSession, user_id: str, notification_keys: list[str]) -> dict[str, NotificationReadState]:
        if not notification_keys:
            return {}
        stmt = select(NotificationReadState).where(
            NotificationReadState.user_id == user_id,
            NotificationReadState.notification_key.in_(notification_keys),
        )
        states = (await db.execute(stmt)).scalars().all()
        return {state.notification_key: state for state in states}

    @staticmethod
    async def history(
        db: AsyncSession,
        *,
        scope_path: str,
        user_id: str,
        since: datetime,
        kind: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        payload = await NotificationService.poll_new_data(db, scope_path, since, per_bucket_limit=limit)
        items: list[dict[str, Any]] = []
        for bucket_kind, rows in payload.items():
            if kind and kind != "all" and bucket_kind != kind:
                continue
            for row in rows:
                source_id = str(row.get("id") or row.get("worker_id") or row.get("user_id") or "")
                notification_key = NotificationService._notification_key(bucket_kind, source_id)
                created_at = row.get("created_at")
                items.append(
                    {
                        "notification_key": notification_key,
                        "source_id": source_id,
                        "kind": bucket_kind,
                        "title": NotificationService._title_for_kind(bucket_kind),
                        "body": NotificationService._body_for_kind(bucket_kind, row),
                        "priority": NotificationService._priority_for_kind(bucket_kind),
                        "created_at": created_at,
                    }
                )
        items.sort(key=lambda row: row.get("created_at") or datetime.now(timezone.utc), reverse=True)
        items = items[:limit]
        state_map = await NotificationService._read_state_map(db, user_id, [item["notification_key"] for item in items])
        for item in items:
            state = state_map.get(item["notification_key"])
            is_read = bool(state and state.read_at)
            item["status"] = "read" if is_read else "unread"
            item["read_at"] = state.read_at if state else None
        return items

    @staticmethod
    async def set_read_state(
        db: AsyncSession,
        *,
        user_id: str,
        notification_key: str,
        read: bool,
    ) -> dict[str, Any]:
        stmt = select(NotificationReadState).where(
            NotificationReadState.user_id == user_id,
            NotificationReadState.notification_key == notification_key,
        )
        state = (await db.execute(stmt)).scalars().first()
        if state is None:
            state = NotificationReadState(
                user_id=user_id,
                notification_key=notification_key,
                read_at=datetime.now(timezone.utc) if read else None,
            )
        else:
            state.read_at = datetime.now(timezone.utc) if read else None
        db.add(state)
        await db.commit()
        await db.refresh(state)
        return {
            "notification_key": notification_key,
            "status": "read" if state.read_at else "unread",
            "read_at": state.read_at,
        }
