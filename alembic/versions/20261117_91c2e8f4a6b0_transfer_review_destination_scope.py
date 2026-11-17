"""Allow transfer review from the receiving location scope.

Revision ID: 91c2e8f4a6b0
Revises: d7a4c1e2f809
Create Date: 2026-11-17
"""

from alembic import op


revision = "91c2e8f4a6b0"
down_revision = "d7a4c1e2f809"
branch_labels = None
depends_on = None


_DESTINATION_SCOPE = """
    NULLIF(current_setting('app.scope_path', true), '') IS NOT NULL
    AND EXISTS (
        SELECT 1
        FROM public.locations AS destination
        WHERE destination.location_id = transfer_requests.to_location_id
          AND (
              destination.path::ltree <@ NULLIF(current_setting('app.scope_path', true), '')::ltree
              OR (
                  COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int <> 8
                  AND NULLIF(current_setting('app.scope_path', true), '')::ltree <@ destination.path::ltree
              )
          )
          AND (
              COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int <> 8
              OR subpath(destination.path::ltree, 0, 2)::text = ANY(
                  string_to_array(NULLIF(current_setting('app.nation_paths', true), ''), '|')
              )
          )
    )
"""


def upgrade() -> None:
    # Existing policies scope requests by their origin path. These additional
    # policies expose a request to the destination's authorized hierarchy so
    # its leaders can review the receiving-location stage. Approval endpoints
    # still enforce the exact stage, role, and hierarchy before changing it.
    op.execute(f"""
        CREATE POLICY church_transfer_requests_destination_read
        ON public.transfer_requests FOR SELECT TO PUBLIC
        USING ({_DESTINATION_SCOPE})
    """)
    op.execute(f"""
        CREATE POLICY church_transfer_requests_destination_update
        ON public.transfer_requests FOR UPDATE TO PUBLIC
        USING ({_DESTINATION_SCOPE})
        WITH CHECK ({_DESTINATION_SCOPE})
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS church_transfer_requests_destination_update ON public.transfer_requests")
    op.execute("DROP POLICY IF EXISTS church_transfer_requests_destination_read ON public.transfer_requests")
