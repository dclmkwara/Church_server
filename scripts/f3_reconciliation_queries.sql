-- Slice F3 independent reconciliation queries.
-- Run against the local restored clone only. These queries read stored rows;
-- they do not call or reproduce application service functions.

-- Q1: six population categories and total by stored approval status.
SELECT date::date AS occurrence_date, program_level, program_scope_path,
       status, count(*) AS rows,
       sum(adult_male) AS adult_male, sum(adult_female) AS adult_female,
       sum(youth_male) AS youth_male, sum(youth_female) AS youth_female,
       sum(boys) AS children_male, sum(girls) AS children_female,
       sum(total) AS submitted_total
FROM counts
WHERE is_deleted IS NOT TRUE
GROUP BY 1,2,3,4
ORDER BY 1,2,3,4;

-- Q1b: counted weekly scope totals. Local reports covered by an approved
-- combined report are suppressed; each combined report is counted once at
-- its stored reporting scope. Pending and rejected rows never enter totals.
-- Replace :scope_path with a path and :start_date/:end_date with the period.
WITH accepted AS (
  SELECT c.*, coalesce(nullif(c.program_scope_path, ''), c.path) AS report_path
  FROM counts c
  WHERE c.status = 'approved' AND c.is_deleted IS NOT TRUE
    AND c.date::date BETWEEN :start_date AND :end_date
), local_rows AS (
  SELECT a.* FROM accepted a
  WHERE lower(coalesce(a.program_level, 'local')) IN ('local', 'location')
    AND a.path LIKE :scope_path || '.%'
    AND NOT EXISTS (
      SELECT 1 FROM accepted combined
      WHERE lower(combined.program_level) IN ('group','region','state')
        AND combined.date::date = a.date::date
        AND a.path LIKE combined.report_path || '.%'
    )
), combined_rows AS (
  SELECT a.* FROM accepted a
  WHERE lower(coalesce(a.program_level,'')) IN ('group','region','state')
    AND (a.report_path = :scope_path OR a.report_path LIKE :scope_path || '.%')
), effective_rows AS (
  SELECT * FROM local_rows UNION ALL SELECT * FROM combined_rows
)
SELECT date::date AS occurrence_date, count(*) AS counted_rows,
       sum(adult_male) AS adult_male, sum(adult_female) AS adult_female,
       sum(youth_male) AS youth_male, sum(youth_female) AS youth_female,
       sum(boys) AS children_male, sum(girls) AS children_female,
       sum(total) AS population
FROM effective_rows
GROUP BY 1 ORDER BY 1;

-- Q2: offerings. Pending remains separate from approved amounts.
SELECT date::date AS occurrence_date, program_type, fund_type, status,
       count(*) AS records, sum(amount) AS amount
FROM offerings
WHERE is_deleted IS NOT TRUE
GROUP BY 1,2,3,4 ORDER BY 1,2,3,4;

-- Q3: worker attendance. expected_workers_count is the per-meeting roster
-- denominator snapshot; do not sum expected worker IDs across meetings.
SELECT date::date AS occurrence_date, program_type,
       count(*) AS submissions,
       sum(expected_workers_count) AS expected_places,
       sum(present_count) AS present,
       count(*) FILTER (WHERE expected_worker_ids IS NOT NULL) AS rows_with_roster_snapshot
FROM worker_attendance_submissions
WHERE is_deleted IS NOT TRUE
GROUP BY 1,2 ORDER BY 1,2;

-- Q4: fellowship attendance remains location-linked and separate.
SELECT fa.date::date AS occurrence_date, f.location_id, fa.fellowship_id,
       count(*) AS records, sum(fa.adult_male) AS adult_male,
       sum(fa.adult_female) AS adult_female, sum(fa.youth_male) AS youth_male,
       sum(fa.youth_female) AS youth_female, sum(fa.boys) AS children_male,
       sum(fa.girls) AS children_female, sum(fa.total) AS total
FROM fellowship_attendance fa
JOIN fellowships f ON f.fellowship_id = fa.fellowship_id
WHERE fa.is_deleted IS NOT TRUE
GROUP BY 1,2,3 ORDER BY 1,2,3;

-- Q5: newcomers/converts are records, not unique-person counts.
SELECT date::date AS occurrence_date, record_type, status, count(*) AS records
FROM records
WHERE is_deleted IS NOT TRUE AND lower(record_type) IN ('newcomer','convert')
GROUP BY 1,2,3 ORDER BY 1,2,3;

-- Q6: event day totals, preserving campaign, event/session and source role.
SELECT e.campaign_id, e.id AS event_id, e.date AS event_date,
       pt.name AS program_type, e.reporting_scope,
       c.source_role, c.status, count(c.id) AS count_records,
       sum(c.adult_male) AS adult_male, sum(c.adult_female) AS adult_female,
       sum(c.youth_male) AS youth_male, sum(c.youth_female) AS youth_female,
       sum(c.boys) AS children_male, sum(c.girls) AS children_female,
       sum(c.total) AS population
FROM program_events e
JOIN program_types pt ON pt.id = e.program_type_id
LEFT JOIN counts c ON c.event_id = e.id AND c.is_deleted IS NOT TRUE
WHERE e.is_deleted IS NOT TRUE AND e.approval_status = 'approved'
GROUP BY 1,2,3,4,5,6,7 ORDER BY 1,3,4,6,7;
