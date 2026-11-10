"""Named thresholds and definitions used by printable Pastor reports."""

MIN_COMPARABLE_LOCATIONS = 5
DECLINE_ATTENTION_PERCENT = 15
CONSECUTIVE_MISSING_SUNDAYS = 2

DEFINITIONS = {
    "counted": "Counted reports are approved by default; pending reports appear only when the filter includes them.",
    "missing": "Missing means no counted report was received; it is never treated as zero.",
    "population": "Documented population is the location's on-paper estimate; attendance can exceed it (visitors, guests).",
    "expected_percent": "Pooled counted attendance divided by pooled documented population for locations with both values; values are not capped.",
    "comparison": "Period changes use the same reporting locations with counted reports in both periods, pooled before calculating the percentage change.",
    "attendance_identity": "Attendance is a head count. People are not registered or matched across locations, so someone counted at two locations is a known limit.",
    "record_counts": "Newcomer and convert metrics count stored records, not unique people. The current record source has no completion flag for a zero-record occurrence, so no records is not evidence of a reported zero.",
}
