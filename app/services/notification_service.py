from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Any

from sqlalchemy import and_, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.filters import scope_filter as _scope_filter, scope_or_ancestor_filter
from app.models.approvals import WorkerRemovalRequest
from app.models.audit import NotificationReadState
from app.models.broadcast import BroadcastMessage
from app.models.core import _LTREE
from app.models.counts import Count, CountGroup, CountReminderRecipient
from app.models.fellowship_activities import FellowshipAttendance, PrayerRequest, Testimony
from app.models.location import Location
from app.models.offerings import Offering
from app.models.user import User, Worker, Role, user_roles
from app.utils.count_groups import count_group_is_past_deadline



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
            "count_reminder": "Sunday attendance report reminder",
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
        if kind == "count_reminder":
            return f"A Sunday attendance report is still needed for {row.get('location_name') or 'your location'} ({row.get('occurrence_date')})."
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
        role_score: int = 1,
    ) -> list[dict[str, Any]]:
        # No scheduler is required: the Location Pastor's notification poll
        # lazily closes elapsed section groups and creates the in-app notice.
        is_location_pastor = bool((await db.execute(
            select(User.user_id).join(user_roles, user_roles.c.user_id == User.user_id)
            .join(Role, Role.id == user_roles.c.role_id)
            .where(User.user_id == user_id, User.is_active.is_(True), User.is_deleted.is_(False),
                   Role.role_name == "Location Pastor", Role.is_deleted.is_(False))
            .limit(1)
        )).scalars().all())
        if is_location_pastor:
            now_lagos = datetime.now(ZoneInfo("Africa/Lagos"))
            open_groups = (await db.execute(select(CountGroup).where(
                CountGroup.reporting_scope_path == scope_path,
                CountGroup.count_mode == "section", CountGroup.state == "open",
                CountGroup.finalized_at.is_(None), CountGroup.auto_closed_at.is_(None),
            ).with_for_update())).scalars().all()
            changed = False
            for group in open_groups:
                if count_group_is_past_deadline(group.occurrence_date, now_lagos):
                    group.state = "complete"
                    group.auto_closed_at = now_lagos
                    changed = True
            if changed:
                await db.commit()
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
        if not kind or kind in {"all", "count_reminder", "count_reminders"}:
            # Reminders are addressed records, not scope broadcasts. Filtering by
            # recipient_user_id prevents parent pastors from inheriting child
            # reminders through their wider jurisdiction.
            reminder_rows = (await db.execute(
                select(CountReminderRecipient, Location.location_name)
                .join(Location, Location.location_id == CountReminderRecipient.location_id)
                .where(
                    CountReminderRecipient.recipient_user_id == user_id,
                    CountReminderRecipient.sent_at > since,
                )
                .order_by(CountReminderRecipient.sent_at.desc())
                .limit(limit)
            )).all()
            for reminder, location_name in reminder_rows:
                source_id = str(reminder.id)
                items.append({
                    "notification_key": NotificationService._notification_key("count_reminder", source_id),
                    "source_id": source_id,
                    "kind": "count_reminder",
                    "title": NotificationService._title_for_kind("count_reminder"),
                    "body": NotificationService._body_for_kind("count_reminder", {
                        "location_name": location_name,
                        "occurrence_date": reminder.occurrence_date.isoformat(),
                    }),
                    "priority": "medium",
                    "created_at": reminder.sent_at,
                })
        if not kind or kind in {"all", "count_group_auto_closed"}:
            # This is a direct in-app notice to the Location Pastor at the exact
            # reporting scope. Parent pastors do not inherit it through ltree.
            auto_closed_rows = (await db.execute(
                select(CountGroup, Location.location_name)
                .join(Location, Location.location_id == CountGroup.location_id)
                .join(User, User.user_id == user_id)
                .join(user_roles, user_roles.c.user_id == User.user_id)
                .join(Role, Role.id == user_roles.c.role_id)
                .where(
                    CountGroup.reporting_scope_path == scope_path,
                    CountGroup.auto_closed_at > since,
                    User.user_id == user_id,
                    User.is_active.is_(True), User.is_deleted.is_(False),
                    Role.role_name == "Location Pastor", Role.is_deleted.is_(False),
                )
                .order_by(CountGroup.auto_closed_at.desc()).limit(limit)
            )).all()
            for group, location_name in auto_closed_rows:
                items.append({
                    "notification_key": NotificationService._notification_key("count_group_auto_closed", str(group.id)),
                    "source_id": str(group.id), "kind": "count_group_auto_closed",
                    "title": "Count group auto-closed",
                    "body": f"The count group for {location_name} on {group.occurrence_date} auto-closed without usher confirmation.",
                    "priority": "medium", "created_at": group.auto_closed_at,
                })
        if not kind or kind in {"all", "broadcast", "broadcasts"}:
            broadcast_rows = (await db.execute(
                select(BroadcastMessage).where(
                    scope_or_ancestor_filter(BroadcastMessage.path, scope_path),
                    BroadcastMessage.is_active.is_(True),
                    BroadcastMessage.sent_at > since,
                ).order_by(BroadcastMessage.sent_at.desc()).limit(limit)
            )).scalars().all()
            for message in broadcast_rows:
                target_path = str(message.path)
                addressed_to_user = target_path == scope_path or scope_path.startswith(target_path + ".")
                if not addressed_to_user and role_score < 3:
                    continue
                if message.audience == "pastors" and role_score < 2:
                    continue
                items.append({
                    "notification_key": NotificationService._notification_key("broadcast", str(message.id)),
                    "source_id": str(message.id),
                    "kind": "broadcast",
                    "title": message.title,
                    "body": message.content,
                    "priority": message.priority,
                    "created_at": message.sent_at,
                })
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
