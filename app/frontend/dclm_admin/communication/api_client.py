from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..backend import BackendClient, BackendClientError
from ..backend.config import BackendConfig, get_backend_config


@dataclass
class APIClient:
    config: BackendConfig | None = None

    def __post_init__(self) -> None:
        if self.config is None:
            self.config = get_backend_config()
        self._backend_client = BackendClient(config=self.config)

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    @property
    def api_base_url(self) -> str:
        return self.config.api_base_url

    async def login(self, *, email: str, password: str) -> dict[str, Any]:
        return await self._backend_client.login(username=email, password=password)

    async def refresh(self, refresh_token: str) -> dict[str, Any]:
        return await self._backend_client.refresh(refresh_token)

    async def get_current_user(self, access_token: str) -> dict[str, Any]:
        return await self._backend_client.get_current_user(access_token)

    async def get_health(self) -> dict[str, Any]:
        return await self._backend_client.get_health()

    async def get_system_metadata(self, access_token: str) -> dict[str, Any]:
        return await self._backend_client.get_system_metadata(access_token)

    async def get_system_metrics(self, access_token: str) -> dict[str, Any]:
        return await self._backend_client.get_system_metrics(access_token)

    async def list_audit_logs(self, access_token: str, *, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return await self._backend_client.list_audit_logs(access_token, skip=skip, limit=limit)

    async def seed_database(self, access_token: str, *, confirm: bool = True) -> dict[str, Any]:
        return await self._backend_client.seed_database(access_token, confirm=confirm)

    async def get_sync_changes(self, access_token: str, *, since: str) -> dict[str, Any]:
        return await self._backend_client.get_sync_changes(access_token, since=since)

    async def list_sync_conflicts(self, access_token: str) -> dict[str, Any]:
        return await self._backend_client.list_sync_conflicts(access_token)

    async def resolve_sync_conflict(self, access_token: str, conflict_id: str, resolution: str) -> dict[str, Any]:
        return await self._backend_client.resolve_sync_conflict(access_token, conflict_id, resolution)

    async def list_public_contact_submissions(
        self,
        access_token: str,
        *,
        status: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await self._backend_client.list_public_contact_submissions(
            access_token,
            status=status,
            search=search,
            skip=skip,
            limit=limit,
        )

    async def review_public_contact_submission(self, access_token: str, submission_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.review_public_contact_submission(access_token, submission_id, payload)

    async def list_public_prayer_submissions(
        self,
        access_token: str,
        *,
        status: str | None = None,
        urgent: bool | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return await self._backend_client.list_public_prayer_submissions(
            access_token,
            status=status,
            urgent=urgent,
            search=search,
            skip=skip,
            limit=limit,
        )

    async def review_public_prayer_submission(self, access_token: str, submission_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.review_public_prayer_submission(access_token, submission_id, payload)

    async def poll_notifications(self, access_token: str, *, since: str) -> dict[str, list[dict[str, Any]]]:
        return await self._backend_client.poll_notifications(access_token, since=since)

    async def get_notification_history(
        self,
        access_token: str,
        *,
        since: str | None = None,
        days: int = 14,
        kind: str = "all",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        return await self._backend_client.get_notification_history(access_token, since=since, days=days, kind=kind, limit=limit)

    async def mark_notification_read(self, access_token: str, notification_key: str) -> dict[str, Any]:
        return await self._backend_client.mark_notification_read(access_token, notification_key)

    async def mark_notification_unread(self, access_token: str, notification_key: str) -> dict[str, Any]:
        return await self._backend_client.mark_notification_unread(access_token, notification_key)

    async def list_app_versions(
        self,
        access_token: str,
        *,
        skip: int = 0,
        limit: int = 100,
        app_name: str | None = None,
        platform: str | None = None,
        version_number: str | None = None,
        release_date: str | None = None,
        is_active: bool | None = None,
        get_last: bool = False,
    ) -> list[dict[str, Any]]:
        return await self._backend_client.list_app_versions(
            access_token,
            skip=skip,
            limit=limit,
            app_name=app_name,
            platform=platform,
            version_number=version_number,
            release_date=release_date,
            is_active=is_active,
            get_last=get_last,
        )

    async def get_app_version(self, access_token: str, version_id: str) -> dict[str, Any]:
        return await self._backend_client.get_app_version(access_token, version_id)

    async def create_app_version(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_app_version(access_token, payload)

    async def update_app_version(self, access_token: str, version_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.update_app_version(access_token, version_id, payload)

    async def list_workers(self, access_token: str, *, scope_path: str | None = None, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return await self._backend_client.list_workers(access_token, scope_path=scope_path, skip=skip, limit=limit)

    async def list_users(self, access_token: str, *, scope_path: str | None = None, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return await self._backend_client.list_users(access_token, scope_path=scope_path, skip=skip, limit=limit)

    async def list_official_appointments(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        search: str | None = None,
        status: str | None = None,
        appointed_role: str | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        return await self._backend_client.list_official_appointments(
            access_token,
            scope_path=scope_path,
            search=search,
            status=status,
            appointed_role=appointed_role,
            skip=skip,
            limit=limit,
        )

    async def get_official_appointment(self, access_token: str, appointment_id: str) -> dict[str, Any]:
        return await self._backend_client.get_official_appointment(access_token, appointment_id)

    async def create_official_appointment(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_official_appointment(access_token, payload)

    async def update_official_appointment(self, access_token: str, appointment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.update_official_appointment(access_token, appointment_id, payload)

    async def revoke_official_appointment(self, access_token: str, appointment_id: str, note: str | None = None) -> dict[str, Any]:
        return await self._backend_client.revoke_official_appointment(access_token, appointment_id, note)

    async def list_members(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
        skip: int = 0,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return await self._backend_client.list_members(
            access_token,
            scope_path=scope_path,
            location_id=location_id,
            skip=skip,
            limit=limit,
        )

    async def get_member(self, access_token: str, member_id: str) -> dict[str, Any]:
        return await self._backend_client.get_member(access_token, member_id)

    async def create_member(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_member(access_token, payload)

    async def list_locations(self, access_token: str, *, skip: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        return await self._backend_client.list_locations(access_token, skip=skip, limit=limit)

    async def list_fellowships(
        self,
        access_token: str,
        *,
        location_id: str | None = None,
        skip: int = 0,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return await self._backend_client.list_fellowships(access_token, location_id=location_id, skip=skip, limit=limit)

    async def get_fellowship(self, access_token: str, fellowship_id: str) -> dict[str, Any]:
        return await self._backend_client.get_fellowship(access_token, fellowship_id)

    async def create_fellowship(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_fellowship(access_token, payload)

    async def list_fellowship_members(self, access_token: str, *, fellowship_id: str, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._backend_client.list_fellowship_members(access_token, fellowship_id=fellowship_id, skip=skip, limit=limit)

    async def create_fellowship_member(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_fellowship_member(access_token, payload)

    async def list_fellowship_attendance(self, access_token: str, *, fellowship_id: str, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._backend_client.list_fellowship_attendance(access_token, fellowship_id=fellowship_id, skip=skip, limit=limit)

    async def create_fellowship_attendance(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_fellowship_attendance(access_token, payload)

    async def list_fellowship_offerings(self, access_token: str, *, fellowship_id: str, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._backend_client.list_fellowship_offerings(access_token, fellowship_id=fellowship_id, skip=skip, limit=limit)

    async def create_fellowship_offering(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_fellowship_offering(access_token, payload)

    async def list_fellowship_testimonies(self, access_token: str, *, fellowship_id: str, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._backend_client.list_fellowship_testimonies(access_token, fellowship_id=fellowship_id, skip=skip, limit=limit)

    async def create_fellowship_testimony(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_fellowship_testimony(access_token, payload)

    async def list_fellowship_prayers(self, access_token: str, *, fellowship_id: str, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._backend_client.list_fellowship_prayers(access_token, fellowship_id=fellowship_id, skip=skip, limit=limit)

    async def create_fellowship_prayer(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_fellowship_prayer(access_token, payload)

    async def list_fellowship_summaries(self, access_token: str, *, fellowship_id: str, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._backend_client.list_fellowship_summaries(access_token, fellowship_id=fellowship_id, skip=skip, limit=limit)

    async def get_location_details(self, access_token: str, location_id: str) -> dict[str, Any]:
        return await self._backend_client.get_location_details(access_token, location_id)

    async def get_location(self, access_token: str, location_id: str) -> dict[str, Any]:
        return await self._backend_client.get_location(access_token, location_id)

    async def update_location(self, access_token: str, location_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.update_location(access_token, location_id, payload)

    async def list_hierarchy_tree(self, access_token: str) -> list[dict[str, Any]]:
        return await self._backend_client.list_hierarchy_tree(access_token)

    async def search_hierarchy(self, access_token: str, query: str) -> list[dict[str, Any]]:
        return await self._backend_client.search_hierarchy(access_token, query)

    async def get_location_profile(self, access_token: str, location_id: str) -> dict[str, Any]:
        return await self._backend_client.get_location_profile(access_token, location_id)

    async def upsert_location_profile(self, access_token: str, location_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.upsert_location_profile(access_token, location_id, payload)

    async def create_worker(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_worker(access_token, payload)

    async def create_user(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_user(access_token, payload)

    async def list_program_events(self, access_token: str, *, scope_path: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return await self._backend_client.list_program_events(access_token, scope_path=scope_path, limit=limit)

    async def get_program_event(self, access_token: str, event_id: str) -> dict[str, Any]:
        return await self._backend_client.get_program_event(access_token, event_id)

    async def create_program_event(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_program_event(access_token, payload)

    async def list_program_campaigns(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        program_domain: str | None = None,
        event_mode: str | None = None,
        status_value: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        return await self._backend_client.list_program_campaigns(
            access_token,
            scope_path=scope_path,
            program_domain=program_domain,
            event_mode=event_mode,
            status_value=status_value,
            limit=limit,
        )

    async def get_program_campaign(self, access_token: str, campaign_id: str) -> dict[str, Any]:
        return await self._backend_client.get_program_campaign(access_token, campaign_id)

    async def create_program_campaign(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_program_campaign(access_token, payload)

    async def list_event_assignments(self, access_token: str, event_id: str) -> list[dict[str, Any]]:
        return await self._backend_client.list_event_assignments(access_token, event_id)

    async def create_event_assignment(self, access_token: str, event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_event_assignment(access_token, event_id, payload)

    async def approve_event_assignment(self, access_token: str, assignment_id: str) -> dict[str, Any]:
        return await self._backend_client.approve_event_assignment(access_token, assignment_id)

    async def reject_event_assignment(self, access_token: str, assignment_id: str, note: str | None = None) -> dict[str, Any]:
        return await self._backend_client.reject_event_assignment(access_token, assignment_id, note)

    async def list_program_domains(self, access_token: str, *, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._backend_client.list_program_domains(access_token, skip=skip, limit=limit)

    async def get_program_domain(self, access_token: str, domain_id: int | str) -> dict[str, Any]:
        return await self._backend_client.get_program_domain(access_token, domain_id)

    async def create_program_domain(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_program_domain(access_token, payload)

    async def list_program_types(
        self,
        access_token: str,
        *,
        domain_id: int | str | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        return await self._backend_client.list_program_types(access_token, domain_id=domain_id, skip=skip, limit=limit)

    async def get_program_type(self, access_token: str, type_id: int | str) -> dict[str, Any]:
        return await self._backend_client.get_program_type(access_token, type_id)

    async def create_program_type(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_program_type(access_token, payload)

    async def list_announcements(
        self,
        access_token: str,
        *,
        meeting: str | None = None,
        is_active: bool | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        return await self._backend_client.list_announcements(access_token, meeting=meeting, is_active=is_active, limit=limit)

    async def get_announcement(self, access_token: str, announcement_id: str) -> dict[str, Any]:
        return await self._backend_client.get_announcement(access_token, announcement_id)

    async def create_announcement(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_announcement(access_token, payload)

    async def update_announcement(self, access_token: str, announcement_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.update_announcement(access_token, announcement_id, payload)

    async def publish_announcement(self, access_token: str, announcement_id: str) -> dict[str, Any]:
        return await self._backend_client.publish_announcement(access_token, announcement_id)

    async def delete_announcement(self, access_token: str, announcement_id: str) -> Any:
        return await self._backend_client.delete_announcement(access_token, announcement_id)

    async def list_media_galleries(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        skip: int = 0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        return await self._backend_client.list_media_galleries(access_token, scope_path=scope_path, skip=skip, limit=limit)

    async def get_media_gallery(self, access_token: str, gallery_id: str) -> dict[str, Any]:
        return await self._backend_client.get_media_gallery(access_token, gallery_id)

    async def create_media_gallery(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_media_gallery(access_token, payload)

    async def delete_media_gallery(self, access_token: str, gallery_id: str) -> Any:
        return await self._backend_client.delete_media_gallery(access_token, gallery_id)

    async def list_media_items(self, access_token: str, *, gallery_id: str, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._backend_client.list_media_items(access_token, gallery_id=gallery_id, skip=skip, limit=limit)

    async def create_media_item(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_media_item(access_token, payload)

    async def delete_media_item(self, access_token: str, item_id: str) -> Any:
        return await self._backend_client.delete_media_item(access_token, item_id)

    async def list_counts(self, access_token: str, *, scope_path: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return await self._backend_client.list_counts(access_token, scope_path=scope_path, limit=limit)

    async def create_count(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_count(access_token, payload)

    async def list_offerings(self, access_token: str, *, scope_path: str | None = None, fund_type: str | None = None, location_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return await self._backend_client.list_offerings(access_token, scope_path=scope_path, fund_type=fund_type, location_id=location_id, limit=limit)

    async def create_offering(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_offering(access_token, payload)

    async def list_records(self, access_token: str, *, scope_path: str | None = None, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._backend_client.list_records(access_token, scope_path=scope_path, skip=skip, limit=limit)

    async def get_record(self, access_token: str, record_id: str) -> dict[str, Any]:
        return await self._backend_client.get_record(access_token, record_id)

    async def create_record(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_record(access_token, payload)

    async def list_attendance(self, access_token: str, *, scope_path: str | None = None, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._backend_client.list_attendance(access_token, scope_path=scope_path, skip=skip, limit=limit)

    async def get_attendance(self, access_token: str, attendance_id: str) -> dict[str, Any]:
        return await self._backend_client.get_attendance(access_token, attendance_id)

    async def create_attendance(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_attendance(access_token, payload)

    async def get_attendance_stats(self, access_token: str, *, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        return await self._backend_client.get_attendance_stats(access_token, start_date=start_date, end_date=end_date)

    async def get_population_statistics(
        self,
        access_token: str,
        *,
        program_domain: str | None = None,
        program_type: str | None = None,
        location_id: str | None = None,
        start_month: int | None = None,
        end_month: int | None = None,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> dict[str, Any]:
        return await self._backend_client.get_population_statistics(
            access_token,
            program_domain=program_domain,
            program_type=program_type,
            location_id=location_id,
            start_month=start_month,
            end_month=end_month,
            start_year=start_year,
            end_year=end_year,
        )

    async def get_church_statistics(self, access_token: str) -> dict[str, Any]:
        return await self._backend_client.get_church_statistics(access_token)

    async def get_user_statistics(self, access_token: str) -> dict[str, Any]:
        return await self._backend_client.get_user_statistics(access_token)

    async def get_dashboard_summary(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._backend_client.get_dashboard_summary(access_token, scope_path=scope_path, location_id=location_id)

    async def get_dashboard_bootstrap(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
        months: int = 12,
        sections: list[str] | None = None,
    ) -> dict[str, Any]:
        return await self._backend_client.get_dashboard_bootstrap(
            access_token,
            scope_path=scope_path,
            location_id=location_id,
            months=months,
            sections=sections,
        )

    async def get_dashboard_member_analytics(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
        months: int = 12,
    ) -> dict[str, Any]:
        return await self._backend_client.get_dashboard_member_analytics(
            access_token,
            scope_path=scope_path,
            location_id=location_id,
            months=months,
        )

    async def get_dashboard_worker_analytics(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
    ) -> dict[str, Any]:
        return await self._backend_client.get_dashboard_worker_analytics(access_token, scope_path=scope_path, location_id=location_id)

    async def get_dashboard_program_comparison(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
        limit: int = 6,
    ) -> dict[str, Any]:
        return await self._backend_client.get_dashboard_program_comparison(
            access_token,
            scope_path=scope_path,
            location_id=location_id,
            limit=limit,
        )

    async def get_dashboard_worker_meeting_comparison(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
        limit: int = 6,
    ) -> dict[str, Any]:
        return await self._backend_client.get_dashboard_worker_meeting_comparison(
            access_token,
            scope_path=scope_path,
            location_id=location_id,
            limit=limit,
        )

    async def get_dashboard_newcomer_analytics(
        self,
        access_token: str,
        *,
        scope_path: str | None = None,
        location_id: str | None = None,
        months: int = 12,
    ) -> dict[str, Any]:
        return await self._backend_client.get_dashboard_newcomer_analytics(
            access_token,
            scope_path=scope_path,
            location_id=location_id,
            months=months,
        )

    async def get_report_summary(self, access_token: str, *, scope_path: str | None = None, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, Any]]:
        return await self._backend_client.get_report_summary(access_token, scope_path=scope_path, start_date=start_date, end_date=end_date)

    async def get_report_financial(self, access_token: str, *, scope_path: str | None = None, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, Any]]:
        return await self._backend_client.get_report_financial(access_token, scope_path=scope_path, start_date=start_date, end_date=end_date)

    async def get_report_attendance(self, access_token: str, *, scope_path: str | None = None, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, Any]]:
        return await self._backend_client.get_report_attendance(access_token, scope_path=scope_path, start_date=start_date, end_date=end_date)

    async def get_report_timeseries(self, access_token: str, *, metric: str, interval: str = "daily", scope_path: str | None = None, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        return await self._backend_client.get_report_timeseries(access_token, metric=metric, interval=interval, scope_path=scope_path, start_date=start_date, end_date=end_date)

    async def get_report_breakdown(self, access_token: str, *, metric: str, level: str, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        return await self._backend_client.get_report_breakdown(access_token, metric=metric, level=level, start_date=start_date, end_date=end_date)

    async def get_report_anomalies(self, access_token: str, *, metric: str = "counts", threshold: float = 2.0, days: int = 30) -> dict[str, Any]:
        return await self._backend_client.get_report_anomalies(access_token, metric=metric, threshold=threshold, days=days)

    async def get_report_growth(self, access_token: str, *, metric: str = "counts", period: str = "monthly", months: int = 12) -> dict[str, Any]:
        return await self._backend_client.get_report_growth(access_token, metric=metric, period=period, months=months)

    async def refresh_reports(self, access_token: str) -> dict[str, Any]:
        return await self._backend_client.refresh_reports(access_token)

    async def export_report_csv(self, access_token: str, *, report_type: str, scope_path: str | None = None, start_date: str | None = None, end_date: str | None = None) -> tuple[bytes, dict[str, str]]:
        return await self._backend_client.export_report_csv(access_token, report_type=report_type, scope_path=scope_path, start_date=start_date, end_date=end_date)

    async def export_report_excel(self, access_token: str, *, report_type: str, start_date: str | None = None, end_date: str | None = None) -> tuple[bytes, dict[str, str]]:
        return await self._backend_client.export_report_excel(access_token, report_type=report_type, start_date=start_date, end_date=end_date)

    async def export_report_pdf(self, access_token: str, *, report_type: str, start_date: str | None = None, end_date: str | None = None) -> tuple[bytes, dict[str, str]]:
        return await self._backend_client.export_report_pdf(access_token, report_type=report_type, start_date=start_date, end_date=end_date)

    async def get_worker(self, access_token: str, worker_id: str) -> dict[str, Any]:
        return await self._backend_client.get_worker(access_token, worker_id)

    async def list_pending_workers(self, access_token: str, *, scope_path: str | None = None, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return await self._backend_client.list_pending_workers(access_token, scope_path=scope_path, skip=skip, limit=limit)

    async def get_user_details(self, access_token: str, user_id: str) -> dict[str, Any]:
        return await self._backend_client.get_user_details(access_token, user_id)

    async def update_user(self, access_token: str, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.update_user(access_token, user_id, payload)

    async def assign_roles(self, access_token: str, user_id: str, role_ids: list[int]) -> dict[str, Any]:
        return await self._backend_client.assign_roles(access_token, user_id, role_ids)

    async def list_available_roles(self, access_token: str) -> list[dict[str, Any]]:
        return await self._backend_client.list_available_roles(access_token)

    async def list_rbac_roles(self, access_token: str, *, skip: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        return await self._backend_client.list_rbac_roles(access_token, skip=skip, limit=limit)

    async def get_rbac_role(self, access_token: str, role_id: int | str) -> dict[str, Any]:
        return await self._backend_client.get_rbac_role(access_token, role_id)

    async def update_rbac_role(self, access_token: str, role_id: int | str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.update_rbac_role(access_token, role_id, payload)

    async def list_rbac_permissions(self, access_token: str, *, skip: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        return await self._backend_client.list_rbac_permissions(access_token, skip=skip, limit=limit)

    async def get_rbac_permission(self, access_token: str, permission_id: int | str) -> dict[str, Any]:
        return await self._backend_client.get_rbac_permission(access_token, permission_id)

    async def list_rbac_scores(self, access_token: str, *, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return await self._backend_client.list_rbac_scores(access_token, skip=skip, limit=limit)

    async def list_pending_users(self, access_token: str, *, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return await self._backend_client.list_pending_users(access_token, skip=skip, limit=limit)

    async def approve_user(self, access_token: str, user_id: str) -> dict[str, Any]:
        return await self._backend_client.approve_user(access_token, user_id)

    async def reject_user(self, access_token: str, user_id: str, reason: str) -> dict[str, Any]:
        return await self._backend_client.reject_user(access_token, user_id, reason)

    async def deactivate_user(self, access_token: str, user_id: str, reason: str | None = None) -> dict[str, Any]:
        return await self._backend_client.deactivate_user(access_token, user_id, reason)

    async def reactivate_user(self, access_token: str, user_id: str) -> dict[str, Any]:
        return await self._backend_client.reactivate_user(access_token, user_id)

    async def approve_worker(self, access_token: str, worker_id: str) -> dict[str, Any]:
        return await self._backend_client.approve_worker(access_token, worker_id)

    async def reject_worker(self, access_token: str, worker_id: str, reason: str) -> dict[str, Any]:
        return await self._backend_client.reject_worker(access_token, worker_id, reason)

    async def list_transfer_requests(self, access_token: str, *, status: str | None = None, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return await self._backend_client.list_transfer_requests(access_token, status=status, skip=skip, limit=limit)

    async def approve_transfer_request(self, access_token: str, request_id: str) -> dict[str, Any]:
        return await self._backend_client.approve_transfer_request(access_token, request_id)

    async def reject_transfer_request(self, access_token: str, request_id: str, reason: str | None = None) -> dict[str, Any]:
        return await self._backend_client.reject_transfer_request(access_token, request_id, reason)

    async def list_status_change_requests(self, access_token: str, *, status: str | None = None, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return await self._backend_client.list_status_change_requests(access_token, status=status, skip=skip, limit=limit)

    async def approve_status_change_request(self, access_token: str, request_id: str) -> dict[str, Any]:
        return await self._backend_client.approve_status_change_request(access_token, request_id)

    async def reject_status_change_request(self, access_token: str, request_id: str, reason: str | None = None) -> dict[str, Any]:
        return await self._backend_client.reject_status_change_request(access_token, request_id, reason)

    async def list_removal_requests(self, access_token: str, *, status: str | None = None, current_level: int | None = None, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return await self._backend_client.list_removal_requests(access_token, status=status, current_level=current_level, skip=skip, limit=limit)

    async def approve_removal_request(self, access_token: str, request_id: str, notes: str | None = None) -> dict[str, Any]:
        return await self._backend_client.approve_removal_request(access_token, request_id, notes)

    async def reject_removal_request(self, access_token: str, request_id: str, notes: str | None = None) -> dict[str, Any]:
        return await self._backend_client.reject_removal_request(access_token, request_id, notes)

    async def escalate_removal_request(self, access_token: str, request_id: str, notes: str) -> dict[str, Any]:
        return await self._backend_client.escalate_removal_request(access_token, request_id, notes)

    async def create_transfer_request(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_transfer_request(access_token, payload)

    async def create_status_change_request(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_status_change_request(access_token, payload)

    async def create_removal_request(self, access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._backend_client.create_removal_request(access_token, payload)


_api_client: APIClient | None = None
_api_client_config_hash: int | None = None


def get_api_client() -> APIClient:
    global _api_client, _api_client_config_hash
    config = get_backend_config()
    config_hash = hash((config.api_base_url, config.enabled))
    if _api_client is None or config_hash != _api_client_config_hash:
        _api_client = APIClient(config=config)
        _api_client_config_hash = config_hash
    return _api_client



__all__ = ["APIClient", "BackendClientError", "get_api_client"]
