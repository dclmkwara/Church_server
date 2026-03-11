# Limitations and Gaps

## Current Limitations
- Public contact/prayer forms are logged but not stored in a dedicated table.
- WebSocket notifications are basic and do not persist events.
- Conflict resolution uses rule-based strategies and may need domain-specific logic.
- Some exports can be heavy without date filters.

## Recommended Improvements
- Add persistence for public forms.
- Add event replay/queue for WebSocket updates.
- Add fine-grained audit logs for approvals.
- Add pagination defaults on all list endpoints.

