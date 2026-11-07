# B3 storage inventory: events, days, program types, and reporting sources

**Status:** completed before B3 page implementation  
**Evidence checked:** SQLAlchemy models and API validation, frontend program service, and read-only aggregate queries against the disposable local clone `dclm_perf`.

## What the current schema represents

| Concept | Stored as | Finding |
|---|---|---|
| Program domain | `program_domains` / `ProgramDomain` | Broad family; `ProgramType.domain_id` ties a type to its domain. |
| Program type | `program_types` / `ProgramType` | A named sub-program such as Bible Study or Crusade Evening. |
| Multi-day series | `program_campaigns` / `ProgramCampaign` | Carries mode, reporting scope, date range, status and optional Alpha location. |
| Dated occurrence | `program_events` / `ProgramEvent` | One program type on one date, linked optionally to a campaign. This expresses a particular Retreat/Crusade day and sub-program when each dated session has an event row. Day number is derivable as `event.date - campaign.start_date + 1`; it is not separately stored. |
| Reporting source | `counts.event_id`, `Count.source_role`, `Count.assignment_id`; `event_assignments` / `EventAssignment` | Counts can link to an event and an assignment. Source roles are alpha, satellite, or regular. For event counts, the server derives role from the event and location; it does not trust a submitted source-role value. |
| Assigned field workers | `event_assignments` / `EventAssignment` | Assignment is to a worker. The assignment path is copied from the event; worker home path is on the Worker record. It is not a distinct expected reporting-unit/zone assignment model. |

Crusade event creation requires both a campaign and an Alpha location. Retreat/Crusade day sessions therefore fit the existing campaign + dated event + program type model. The current models do not hold a separate planned-session catalog or an expected-session list. Per the brief, B3 will show observed “sessions reported” and “planned sessions not defined”; it will not infer missing sessions from the campaign date span.

## Local clone sample (synthetic development data)

Read-only counts from `dclm_perf`:

- 2 active campaign rows: one Retreat campaign (`reporting_scope=region`, date range 2026-10-31 through 2026-11-01) and one Weekly Programs campaign.
- 3 dated event rows, all regular weekly types (Thursday Revival, Sunday Worship, Monday Bible Study); no Retreat or Crusade event rows.
- 0 event assignments.
- 10 count rows with no `event_id`; no event-linked count submissions. The rows are pending synthetic/test records, not production evidence.

The local data therefore cannot demonstrate Retreat/Crusade source coverage or populated event matrices. Screenshots will show explicit empty states for those data gaps rather than treating them as zero turnout.

## Existing campaign report limitation

`ProgramService.campaign_activity()` currently fetches all campaign count rows, then calculates `total_population` by summing every count row across all event dates. Its campaign page labels that total “Population” and also charts per-event totals. This is useful as an operations summary but conflicts with B3’s rule that attendance is never summed across sessions. The new Retreat/Crusade views must present each event/day cell separately and must not use this campaign-wide population total as attendance. The existing campaign report is left intact in this slice; correcting or replacing it requires a separate compatibility decision.

## Smallest schema change

No schema change is needed for the B3 requirement “event + day + program type”: `ProgramEvent.date`, `ProgramEvent.program_type_id`, and optional `campaign_id` already encode it. A separate planned-session model would be needed only when church leadership wants explicit planned/expected sessions; B3 explicitly defers that definition. Likewise, assignment rows are worker assignments, not reporting-unit expectations; pages will not interpret their count as complete location coverage. Crusade Alpha can be read from the event; satellite reporting can be identified from count source role and scoped location path, with unknown coverage when no assignments define it.

## B3 implementation boundary

- Add a parameterized, permission-scoped occurrence read endpoint and use it for weekly configs and event analytics.
- Build Retreat and Crusade event/day matrices, preserving Alpha and satellite as adjacent labelled values and never summing attendance across days.
- Build the Tuesday Leaders Meeting page separately from Saturday Workers Meeting.
- Keep the existing app shell/sidebar and do not add menu entries in B3.
- Do not add expectation rows, split-count behavior, worker attendance roster metrics, or synthetic event reports.
