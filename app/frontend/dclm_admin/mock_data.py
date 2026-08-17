from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any


TODAY = date(2026, 3, 22)


LOCATIONS = [
    {
        "continent": "West Africa Division",
        "nation": "Nigeria",
        "state": "Kwara State",
        "region": "Ilorin North Region",
        "group": "Ilorin East Group",
        "location": "GRA DLBC",
        "path": "global.west_africa.nigeria.kwara_state.ilorin_north_region.ilorin_east_group.gra_dlbc",
    },
    {
        "continent": "West Africa Division",
        "nation": "Nigeria",
        "state": "Kwara State",
        "region": "Ilorin North Region",
        "group": "Ilorin East Group",
        "location": "University DLBC",
        "path": "global.west_africa.nigeria.kwara_state.ilorin_north_region.ilorin_east_group.university_dlbc",
    },
    {
        "continent": "West Africa Division",
        "nation": "Nigeria",
        "state": "Kwara State",
        "region": "Ilorin North Region",
        "group": "Ilorin East Group",
        "location": "Tanke DLBC",
        "path": "global.west_africa.nigeria.kwara_state.ilorin_north_region.ilorin_east_group.tanke_dlbc",
    },
    {
        "continent": "West Africa Division",
        "nation": "Nigeria",
        "state": "Kwara State",
        "region": "Ilorin North Region",
        "group": "Ilorin East Group",
        "location": "Hill DLCF",
        "path": "global.west_africa.nigeria.kwara_state.ilorin_north_region.ilorin_east_group.hill_dlcf",
    },
    {
        "continent": "West Africa Division",
        "nation": "Nigeria",
        "state": "Kwara State",
        "region": "Offa Region",
        "group": "Offa Central Group",
        "location": "Offa Township DLBC",
        "path": "global.west_africa.nigeria.kwara_state.offa_region.offa_central_group.offa_township_dlbc",
    },
    {
        "continent": "West Africa Division",
        "nation": "Nigeria",
        "state": "Lagos State",
        "region": "Ikeja Region",
        "group": "Surulere Group",
        "location": "Surulere DLBC",
        "path": "global.west_africa.nigeria.lagos_state.ikeja_region.surulere_group.surulere_dlbc",
    },
]

LOCATION_LOOKUP = {row["location"]: row for row in LOCATIONS}

SCOPE_PATHS = {
    "global": {"Global": "global"},
    "continent": {"West Africa Division": "global.west_africa"},
    "nation": {"Nigeria": "global.west_africa.nigeria"},
    "state": {
        "Kwara State": "global.west_africa.nigeria.kwara_state",
        "Lagos State": "global.west_africa.nigeria.lagos_state",
    },
    "region": {
        "Ilorin North Region": "global.west_africa.nigeria.kwara_state.ilorin_north_region",
        "Offa Region": "global.west_africa.nigeria.kwara_state.offa_region",
        "Ikeja Region": "global.west_africa.nigeria.lagos_state.ikeja_region",
    },
    "group": {
        "Ilorin East Group": "global.west_africa.nigeria.kwara_state.ilorin_north_region.ilorin_east_group",
        "Offa Central Group": "global.west_africa.nigeria.kwara_state.offa_region.offa_central_group",
        "Surulere Group": "global.west_africa.nigeria.lagos_state.ikeja_region.surulere_group",
    },
    "location": {row["location"]: row["path"] for row in LOCATIONS},
}

BASE_PROGRAM_DOMAINS = [
    {
        "domain_id": "dom-001",
        "name": "Sunday Services",
        "description": "Weekly Sunday worship and teaching meetings.",
    },
    {
        "domain_id": "dom-002",
        "name": "Midweek Meetings",
        "description": "Bible study, revival hour, and weekday teaching meetings.",
    },
    {
        "domain_id": "dom-003",
        "name": "Fellowship Meetings",
        "description": "Smaller fellowship and home care gatherings.",
    },
]

BASE_PROGRAM_TYPES = [
    {
        "type_id": "typ-001",
        "domain_id": "dom-001",
        "domain_name": "Sunday Services",
        "name": "Sunday Worship Service",
        "description": "Main worship service held on Sundays.",
    },
    {
        "type_id": "typ-002",
        "domain_id": "dom-002",
        "domain_name": "Midweek Meetings",
        "name": "Bible Study",
        "description": "Midweek Bible study service.",
    },
    {
        "type_id": "typ-003",
        "domain_id": "dom-003",
        "domain_name": "Fellowship Meetings",
        "name": "Home Care Fellowship",
        "description": "Smaller care group and fellowship gathering.",
    },
]

BASE_PROGRAM_EVENTS = [
    {
        "event_id": "evt-sws-0322",
        "title": "Sunday Worship Service",
        "domain_id": "dom-001",
        "domain_name": "Sunday Services",
        "type_id": "typ-001",
        "program_type": "Sunday Worship Service",
        "date": "2026-03-22",
        "status": "completed",
        "level": "location",
        "location": "GRA DLBC",
        "created_by": "Pastor Samuel Adebayo",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "event_id": "evt-mbs-0324",
        "title": "Monday Bible Study",
        "domain_id": "dom-002",
        "domain_name": "Midweek Meetings",
        "type_id": "typ-002",
        "program_type": "Bible Study",
        "date": "2026-03-24",
        "status": "scheduled",
        "level": "location",
        "location": "GRA DLBC",
        "created_by": "Pastor Samuel Adebayo",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "event_id": "evt-hcf-0326",
        "title": "Home Care Fellowship",
        "domain_id": "dom-003",
        "domain_name": "Fellowship Meetings",
        "type_id": "typ-003",
        "program_type": "Home Care Fellowship",
        "date": "2026-03-26",
        "status": "scheduled",
        "level": "location",
        "location": "GRA DLBC",
        "created_by": "Brother Kehinde Bello",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "event_id": "evt-sws-0322-uni",
        "title": "Sunday Worship Service",
        "domain_id": "dom-001",
        "domain_name": "Sunday Services",
        "type_id": "typ-001",
        "program_type": "Sunday Worship Service",
        "date": "2026-03-22",
        "status": "completed",
        "level": "location",
        "location": "University DLBC",
        "created_by": "Pastor Deborah Yusuf",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
]

BASE_WORKERS = [
    {
        "worker_id": "wrk-001",
        "user_id": "W-001",
        "name": "Adebayo Oluwaseun",
        "gender": "Male",
        "phone": "+234 803 111 1001",
        "unit": "Ushering",
        "status": "Active",
        "approval_status": "approved",
        "location": "GRA DLBC",
        "group": "Ilorin East Group",
        "region": "Ilorin North Region",
        "state": "Kwara State",
        "added_date": "2026-01-12",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "worker_id": "wrk-002",
        "user_id": "W-002",
        "name": "Fatima Hassan",
        "gender": "Female",
        "phone": "+234 803 111 1002",
        "unit": "Choir",
        "status": "Active",
        "approval_status": "approved",
        "location": "GRA DLBC",
        "group": "Ilorin East Group",
        "region": "Ilorin North Region",
        "state": "Kwara State",
        "added_date": "2026-01-20",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "worker_id": "wrk-003",
        "user_id": "W-003",
        "name": "Emmanuel Okafor",
        "gender": "Male",
        "phone": "+234 803 111 1003",
        "unit": "Media",
        "status": "Pending Verification",
        "approval_status": "pending_verification",
        "location": "GRA DLBC",
        "group": "Ilorin East Group",
        "region": "Ilorin North Region",
        "state": "Kwara State",
        "added_date": "2026-03-18",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "worker_id": "wrk-004",
        "user_id": "W-004",
        "name": "Blessing Ihejirika",
        "gender": "Female",
        "phone": "+234 803 111 1004",
        "unit": "Prayer",
        "status": "Active",
        "approval_status": "approved",
        "location": "University DLBC",
        "group": "Ilorin East Group",
        "region": "Ilorin North Region",
        "state": "Kwara State",
        "added_date": "2026-02-01",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "worker_id": "wrk-005",
        "user_id": "W-005",
        "name": "Michael Adesola",
        "gender": "Male",
        "phone": "+234 803 111 1005",
        "unit": "Music",
        "status": "Active",
        "approval_status": "approved",
        "location": "Tanke DLBC",
        "group": "Ilorin East Group",
        "region": "Ilorin North Region",
        "state": "Kwara State",
        "added_date": "2026-01-28",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
    },
    {
        "worker_id": "wrk-006",
        "user_id": "W-006",
        "name": "Grace Oluwatobi",
        "gender": "Female",
        "phone": "+234 803 111 1006",
        "unit": "Children",
        "status": "Active",
        "approval_status": "approved",
        "location": "Hill DLCF",
        "group": "Ilorin East Group",
        "region": "Ilorin North Region",
        "state": "Kwara State",
        "added_date": "2026-02-10",
        "path": LOCATION_LOOKUP["Hill DLCF"]["path"],
    },
    {
        "worker_id": "wrk-007",
        "user_id": "W-007",
        "name": "Isaac Abiodun",
        "gender": "Male",
        "phone": "+234 803 111 1007",
        "unit": "Welfare",
        "status": "Inactive",
        "approval_status": "approved",
        "location": "Offa Township DLBC",
        "group": "Offa Central Group",
        "region": "Offa Region",
        "state": "Kwara State",
        "added_date": "2026-01-15",
        "path": LOCATION_LOOKUP["Offa Township DLBC"]["path"],
    },
    {
        "worker_id": "wrk-008",
        "user_id": "W-008",
        "name": "Folake Adeyemi",
        "gender": "Female",
        "phone": "+234 803 111 1008",
        "unit": "Evangelism",
        "status": "Active",
        "approval_status": "approved",
        "location": "Surulere DLBC",
        "group": "Surulere Group",
        "region": "Ikeja Region",
        "state": "Lagos State",
        "added_date": "2026-02-14",
        "path": LOCATION_LOOKUP["Surulere DLBC"]["path"],
    },
]

BASE_COUNTS = [
    {
        "count_id": "cnt-001",
        "event_title": "Sunday Worship Service",
        "event_id": "evt-sws-0322",
        "date": "2026-03-22",
        "location": "GRA DLBC",
        "group": "Ilorin East Group",
        "region": "Ilorin North Region",
        "state": "Kwara State",
        "adult_male": 124,
        "adult_female": 98,
        "youth_male": 45,
        "youth_female": 37,
        "boys": 22,
        "girls": 19,
        "total": 345,
        "submitted_by": "Pastor Samuel Adebayo",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "count_id": "cnt-002",
        "event_title": "Sunday Worship Service",
        "event_id": "evt-sws-0322",
        "date": "2026-03-22",
        "location": "University DLBC",
        "group": "Ilorin East Group",
        "region": "Ilorin North Region",
        "state": "Kwara State",
        "adult_male": 79,
        "adult_female": 85,
        "youth_male": 32,
        "youth_female": 29,
        "boys": 12,
        "girls": 10,
        "total": 247,
        "submitted_by": "Pastor Deborah Yusuf",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "count_id": "cnt-003",
        "event_title": "Sunday Worship Service",
        "event_id": "evt-sws-0322",
        "date": "2026-03-22",
        "location": "Tanke DLBC",
        "group": "Ilorin East Group",
        "region": "Ilorin North Region",
        "state": "Kwara State",
        "adult_male": 103,
        "adult_female": 118,
        "youth_male": 44,
        "youth_female": 40,
        "boys": 16,
        "girls": 14,
        "total": 335,
        "submitted_by": "Pastor David Akinwale",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
    },
    {
        "count_id": "cnt-004",
        "event_title": "Monday Bible Study",
        "event_id": "evt-mbs-0324",
        "date": "2026-03-17",
        "location": "GRA DLBC",
        "group": "Ilorin East Group",
        "region": "Ilorin North Region",
        "state": "Kwara State",
        "adult_male": 71,
        "adult_female": 84,
        "youth_male": 31,
        "youth_female": 22,
        "boys": 8,
        "girls": 7,
        "total": 223,
        "submitted_by": "Brother Adebayo Oluwaseun",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "count_id": "cnt-005",
        "event_title": "Sunday Worship Service",
        "event_id": "evt-sws-0322",
        "date": "2026-03-22",
        "location": "Offa Township DLBC",
        "group": "Offa Central Group",
        "region": "Offa Region",
        "state": "Kwara State",
        "adult_male": 89,
        "adult_female": 92,
        "youth_male": 38,
        "youth_female": 30,
        "boys": 14,
        "girls": 10,
        "total": 273,
        "submitted_by": "Pastor Isaac Oni",
        "path": LOCATION_LOOKUP["Offa Township DLBC"]["path"],
    },
]

BASE_USERS = [
    {
        "account_id": "usr-001",
        "name": "Adebayo Oluwaseun",
        "phone": "+234 803 111 1001",
        "location": "GRA DLBC",
        "roles": ["Location Worker"],
        "approval_status": "approved",
        "status": "active",
        "worker_id": "wrk-001",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "account_id": "usr-002",
        "name": "Fatima Hassan",
        "phone": "+234 803 111 1002",
        "location": "GRA DLBC",
        "roles": ["Choir Admin"],
        "approval_status": "approved",
        "status": "active",
        "worker_id": "wrk-002",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "account_id": "usr-003",
        "name": "Esther Bamidele",
        "phone": "+234 803 111 1015",
        "location": "GRA DLBC",
        "roles": ["Location Worker"],
        "approval_status": "pending",
        "status": "inactive",
        "worker_id": "wrk-009",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "account_id": "usr-004",
        "name": "Blessing Ihejirika",
        "phone": "+234 803 111 1004",
        "location": "University DLBC",
        "roles": ["Group Admin"],
        "approval_status": "approved",
        "status": "active",
        "worker_id": "wrk-004",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "account_id": "usr-005",
        "name": "Isaac Abiodun",
        "phone": "+234 803 111 1007",
        "location": "Offa Township DLBC",
        "roles": ["Location Worker"],
        "approval_status": "approved",
        "status": "suspended",
        "worker_id": "wrk-007",
        "path": LOCATION_LOOKUP["Offa Township DLBC"]["path"],
    },
]

BASE_OFFICIAL_APPOINTMENTS = [
    {
        "appointment_id": "off-001",
        "worker_id": "wrk-002",
        "worker_name": "Fatima Hassan",
        "appointed_role": "Follow-up Coordinator",
        "assigned_scope": "Ilorin East Group",
        "appointed_by": "Pastor Deborah Yusuf",
        "appointment_date": "2026-02-18",
        "status": "active",
        "location": "GRA DLBC",
        "path": SCOPE_PATHS["group"]["Ilorin East Group"],
    },
    {
        "appointment_id": "off-002",
        "worker_id": "wrk-004",
        "worker_name": "Blessing Ihejirika",
        "appointed_role": "Campus Prayer Secretary",
        "assigned_scope": "University DLBC",
        "appointed_by": "Pastor Deborah Yusuf",
        "appointment_date": "2026-03-02",
        "status": "active",
        "location": "University DLBC",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "appointment_id": "off-003",
        "worker_id": "wrk-007",
        "worker_name": "Isaac Abiodun",
        "appointed_role": "Welfare Assistant",
        "assigned_scope": "Offa Region",
        "appointed_by": "Pastor Grace Omoniyi",
        "appointment_date": "2026-01-26",
        "status": "revoked",
        "location": "Offa Township DLBC",
        "path": SCOPE_PATHS["region"]["Offa Region"],
    },
]

BASE_FELLOWSHIPS = [
    {
        "fellowship_id": "fel-001",
        "name": "Victory Home Fellowship",
        "location": "GRA DLBC",
        "leader_name": "Sister Funke Adeyemi",
        "assistant_name": "Brother Tunde Salawu",
        "meeting_day": "Wednesday",
        "meeting_time": "5:30 PM",
        "next_meeting": "2026-03-25",
        "status": "active",
        "description": "Main neighborhood house fellowship for members around GRA and nearby estates.",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "fellowship_id": "fel-002",
        "name": "Campus Light Fellowship",
        "location": "University DLBC",
        "leader_name": "Brother Kehinde Bello",
        "assistant_name": "Sister Mary Ojo",
        "meeting_day": "Tuesday",
        "meeting_time": "6:00 PM",
        "next_meeting": "2026-03-24",
        "status": "active",
        "description": "Student-focused fellowship for hostel zones and off-campus follow-up.",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "fellowship_id": "fel-003",
        "name": "Tanke Family Fellowship",
        "location": "Tanke DLBC",
        "leader_name": "Sister Esther Bamidele",
        "assistant_name": "Brother Samuel Omoniyi",
        "meeting_day": "Thursday",
        "meeting_time": "5:00 PM",
        "next_meeting": "2026-03-26",
        "status": "active",
        "description": "Family-centered fellowship for the Tanke axis and surrounding streets.",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
    },
    {
        "fellowship_id": "fel-004",
        "name": "Hill Young Adults Fellowship",
        "location": "Hill DLCF",
        "leader_name": "Brother Daniel Olanrewaju",
        "assistant_name": "Sister Grace Oluwatobi",
        "meeting_day": "Friday",
        "meeting_time": "5:30 PM",
        "next_meeting": "2026-03-27",
        "status": "active",
        "description": "Young adult fellowship supporting campus graduates and early-career workers.",
        "path": LOCATION_LOOKUP["Hill DLCF"]["path"],
    },
]

BASE_LOCATION_PROFILES = [
    {
        "location_key": "gra_dlbc",
        "location": "GRA DLBC",
        "church_type": "DLBC",
        "address": "12 Unity Road, GRA, Ilorin, Kwara State",
        "pastor_name": "Pastor Samuel Adebayo",
        "assistant_name": "Brother Tunde Salawu",
        "phone": "+234 803 000 1001",
        "status": "active",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
        "group": "Ilorin East Group",
        "region": "Ilorin North Region",
        "state": "Kwara State",
        "nation": "Nigeria",
        "continent": "West Africa Division",
    },
    {
        "location_key": "university_dlbc",
        "location": "University DLBC",
        "church_type": "DLBC",
        "address": "Opposite Main Gate, University Road, Ilorin, Kwara State",
        "pastor_name": "Pastor Deborah Yusuf",
        "assistant_name": "Brother Kehinde Bello",
        "phone": "+234 803 000 1002",
        "status": "active",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
        "group": "Ilorin East Group",
        "region": "Ilorin North Region",
        "state": "Kwara State",
        "nation": "Nigeria",
        "continent": "West Africa Division",
    },
    {
        "location_key": "tanke_dlbc",
        "location": "Tanke DLBC",
        "church_type": "DLBC",
        "address": "7 Harmony Close, Tanke Junction, Ilorin, Kwara State",
        "pastor_name": "Pastor David Akinwale",
        "assistant_name": "Sister Esther Bamidele",
        "phone": "+234 803 000 1003",
        "status": "active",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
        "group": "Ilorin East Group",
        "region": "Ilorin North Region",
        "state": "Kwara State",
        "nation": "Nigeria",
        "continent": "West Africa Division",
    },
    {
        "location_key": "hill_dlcf",
        "location": "Hill DLCF",
        "church_type": "DLCF",
        "address": "Hill Campus Axis, Ilorin, Kwara State",
        "pastor_name": "Brother Daniel Olanrewaju",
        "assistant_name": "Sister Grace Oluwatobi",
        "phone": "+234 803 000 1004",
        "status": "active",
        "path": LOCATION_LOOKUP["Hill DLCF"]["path"],
        "group": "Ilorin East Group",
        "region": "Ilorin North Region",
        "state": "Kwara State",
        "nation": "Nigeria",
        "continent": "West Africa Division",
    },
    {
        "location_key": "offa_township_dlbc",
        "location": "Offa Township DLBC",
        "church_type": "DLBC",
        "address": "3 Gospel Avenue, Offa Township, Kwara State",
        "pastor_name": "Pastor Isaac Oni",
        "assistant_name": "Brother Samuel Ajayi",
        "phone": "+234 803 000 1005",
        "status": "active",
        "path": LOCATION_LOOKUP["Offa Township DLBC"]["path"],
        "group": "Offa Central Group",
        "region": "Offa Region",
        "state": "Kwara State",
        "nation": "Nigeria",
        "continent": "West Africa Division",
    },
    {
        "location_key": "surulere_dlbc",
        "location": "Surulere DLBC",
        "church_type": "DLBC",
        "address": "16 Chapel Street, Surulere, Lagos State",
        "pastor_name": "Pastor Folorunsho Adeniyi",
        "assistant_name": "Sister Yetunde Alabi",
        "phone": "+234 803 000 1006",
        "status": "active",
        "path": LOCATION_LOOKUP["Surulere DLBC"]["path"],
        "group": "Surulere Group",
        "region": "Ikeja Region",
        "state": "Lagos State",
        "nation": "Nigeria",
        "continent": "West Africa Division",
    },
]

BASE_CHURCH_MEMBERS = [
    {
        "member_id": "mem-001",
        "name": "Mary Oluwabukola",
        "phone": "+234 803 310 1001",
        "gender": "Female",
        "marital_status": "Single",
        "location": "GRA DLBC",
        "fellowship_id": "fel-001",
        "fellowship_name": "Victory Home Fellowship",
        "status": "active",
        "date_joined": "2025-11-10",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "member_id": "mem-002",
        "name": "John Akinlolu",
        "phone": "+234 803 310 1002",
        "gender": "Male",
        "marital_status": "Married",
        "location": "GRA DLBC",
        "fellowship_id": "fel-001",
        "fellowship_name": "Victory Home Fellowship",
        "status": "active",
        "date_joined": "2024-08-03",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "member_id": "mem-003",
        "name": "Deborah Chukwuma",
        "phone": "+234 803 310 1003",
        "gender": "Female",
        "marital_status": "Single",
        "location": "University DLBC",
        "fellowship_id": "fel-002",
        "fellowship_name": "Campus Light Fellowship",
        "status": "active",
        "date_joined": "2025-01-18",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "member_id": "mem-004",
        "name": "Peter Danjuma",
        "phone": "+234 803 310 1004",
        "gender": "Male",
        "marital_status": "Single",
        "location": "University DLBC",
        "fellowship_id": "fel-002",
        "fellowship_name": "Campus Light Fellowship",
        "status": "transferred",
        "date_joined": "2024-09-12",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "member_id": "mem-005",
        "name": "Folake Bamidele",
        "phone": "+234 803 310 1005",
        "gender": "Female",
        "marital_status": "Married",
        "location": "Tanke DLBC",
        "fellowship_id": "fel-003",
        "fellowship_name": "Tanke Family Fellowship",
        "status": "active",
        "date_joined": "2023-05-21",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
    },
    {
        "member_id": "mem-006",
        "name": "Joseph Afolayan",
        "phone": "+234 803 310 1006",
        "gender": "Male",
        "marital_status": "Married",
        "location": "Tanke DLBC",
        "fellowship_id": "fel-003",
        "fellowship_name": "Tanke Family Fellowship",
        "status": "active",
        "date_joined": "2022-07-09",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
    },
    {
        "member_id": "mem-007",
        "name": "Precious Omoniyi",
        "phone": "+234 803 310 1007",
        "gender": "Female",
        "marital_status": "Single",
        "location": "Hill DLCF",
        "fellowship_id": "fel-004",
        "fellowship_name": "Hill Young Adults Fellowship",
        "status": "active",
        "date_joined": "2025-06-14",
        "path": LOCATION_LOOKUP["Hill DLCF"]["path"],
    },
    {
        "member_id": "mem-008",
        "name": "Tosin Adeoti",
        "phone": "+234 803 310 1008",
        "gender": "Male",
        "marital_status": "Single",
        "location": "Hill DLCF",
        "fellowship_id": "fel-004",
        "fellowship_name": "Hill Young Adults Fellowship",
        "status": "inactive",
        "date_joined": "2024-10-01",
        "path": LOCATION_LOOKUP["Hill DLCF"]["path"],
    },
]

BASE_FELLOWSHIP_ATTENDANCE = [
    {
        "record_id": "fsa-001",
        "fellowship_id": "fel-001",
        "date": "2026-03-18",
        "men": 14,
        "women": 18,
        "youths": 6,
        "children": 4,
        "total": 42,
        "submitted_by": "Sister Funke Adeyemi",
        "location": "GRA DLBC",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "record_id": "fsa-002",
        "fellowship_id": "fel-002",
        "date": "2026-03-17",
        "men": 11,
        "women": 15,
        "youths": 12,
        "children": 0,
        "total": 38,
        "submitted_by": "Brother Kehinde Bello",
        "location": "University DLBC",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "record_id": "fsa-003",
        "fellowship_id": "fel-003",
        "date": "2026-03-19",
        "men": 10,
        "women": 13,
        "youths": 5,
        "children": 7,
        "total": 35,
        "submitted_by": "Sister Esther Bamidele",
        "location": "Tanke DLBC",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
    },
    {
        "record_id": "fsa-004",
        "fellowship_id": "fel-004",
        "date": "2026-03-20",
        "men": 9,
        "women": 12,
        "youths": 14,
        "children": 1,
        "total": 36,
        "submitted_by": "Brother Daniel Olanrewaju",
        "location": "Hill DLCF",
        "path": LOCATION_LOOKUP["Hill DLCF"]["path"],
    },
]

BASE_FELLOWSHIP_OFFERINGS = [
    {
        "offering_id": "fso-001",
        "fellowship_id": "fel-001",
        "date": "2026-03-18",
        "amount": 28500,
        "method": "Cash",
        "submitted_by": "Brother Tunde Salawu",
        "location": "GRA DLBC",
        "notes": "Neighborhood fellowship offering counted after closing prayer.",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "offering_id": "fso-002",
        "fellowship_id": "fel-002",
        "date": "2026-03-17",
        "amount": 21400,
        "method": "Transfer",
        "submitted_by": "Sister Mary Ojo",
        "location": "University DLBC",
        "notes": "Included hostel transfer confirmations.",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "offering_id": "fso-003",
        "fellowship_id": "fel-003",
        "date": "2026-03-19",
        "amount": 24750,
        "method": "Cash",
        "submitted_by": "Brother Samuel Omoniyi",
        "location": "Tanke DLBC",
        "notes": "Family fellowship weekly offering.",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
    },
]

BASE_FELLOWSHIP_TESTIMONIES = [
    {
        "testimony_id": "fst-001",
        "fellowship_id": "fel-001",
        "member_name": "Mary Oluwabukola",
        "summary": "God provided a new job offer after the fellowship prayed last month.",
        "date": "2026-03-18",
        "status": "shared",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "testimony_id": "fst-002",
        "fellowship_id": "fel-002",
        "member_name": "Deborah Chukwuma",
        "summary": "Successful end-of-semester exams after dedicated prayer support.",
        "date": "2026-03-17",
        "status": "shared",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
]

BASE_FELLOWSHIP_PRAYERS = [
    {
        "prayer_id": "fsp-001",
        "fellowship_id": "fel-001",
        "requester_name": "John Akinlolu",
        "summary": "Prayer for recovery after minor surgery this week.",
        "date": "2026-03-18",
        "status": "ongoing",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "prayer_id": "fsp-002",
        "fellowship_id": "fel-002",
        "requester_name": "Deborah Chukwuma",
        "summary": "Prayer for new students responding to follow-up in the hostels.",
        "date": "2026-03-17",
        "status": "new",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "prayer_id": "fsp-003",
        "fellowship_id": "fel-003",
        "requester_name": "Folake Bamidele",
        "summary": "Prayer for a sister trusting God for safe delivery.",
        "date": "2026-03-19",
        "status": "answered",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
    },
]

BASE_FELLOWSHIP_SUMMARIES = [
    {
        "summary_id": "fss-001",
        "fellowship_id": "fel-001",
        "week_of": "2026-03-16",
        "average_attendance": 41,
        "homes_visited": 6,
        "newcomers": 2,
        "converts": 1,
        "submitted_by": "Sister Funke Adeyemi",
        "remarks": "Steady neighborhood attendance with two new homes reached.",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "summary_id": "fss-002",
        "fellowship_id": "fel-002",
        "week_of": "2026-03-16",
        "average_attendance": 37,
        "homes_visited": 4,
        "newcomers": 3,
        "converts": 1,
        "submitted_by": "Brother Kehinde Bello",
        "remarks": "Campus outreach is bringing in more first-time students.",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "summary_id": "fss-003",
        "fellowship_id": "fel-003",
        "week_of": "2026-03-16",
        "average_attendance": 34,
        "homes_visited": 5,
        "newcomers": 1,
        "converts": 0,
        "submitted_by": "Sister Esther Bamidele",
        "remarks": "Family attendance is stable and visitation follow-up is improving.",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
    },
]

BASE_FINANCE = [
    {
        "entry_id": "fin-001",
        "fund_type": "offering",
        "amount": 87500,
        "date": "2026-03-22",
        "method": "Cash",
        "event_title": "Sunday Worship Service",
        "location": "GRA DLBC",
        "submitted_by": "Pastor Samuel Adebayo",
        "notes": "Main service offering counted with treasury team.",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "entry_id": "fin-002",
        "fund_type": "tithe",
        "amount": 245000,
        "date": "2026-03-22",
        "method": "Transfer",
        "event_title": "Sunday Worship Service",
        "location": "GRA DLBC",
        "submitted_by": "Brother Tunde Salawu",
        "notes": "Includes bank transfer confirmations received after service.",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "entry_id": "fin-003",
        "fund_type": "offering",
        "amount": 64300,
        "date": "2026-03-22",
        "method": "Cash",
        "event_title": "Sunday Worship Service",
        "location": "University DLBC",
        "submitted_by": "Pastor Deborah Yusuf",
        "notes": "Student service collection.",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "entry_id": "fin-004",
        "fund_type": "tithe",
        "amount": 118500,
        "date": "2026-03-17",
        "method": "Cash",
        "event_title": "Monday Bible Study",
        "location": "Tanke DLBC",
        "submitted_by": "Pastor David Akinwale",
        "notes": "Midweek tithe entries recorded after close of meeting.",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
    },
]

BASE_RECORDS = [
    {
        "record_id": "rec-001",
        "record_type": "newcomer",
        "name": "Mary Oluwabukola",
        "phone": "+234 803 222 1001",
        "gender": "Female",
        "location": "GRA DLBC",
        "status": "follow_up_pending",
        "date": "2026-03-22",
        "service": "Sunday Worship Service",
        "assigned_to": "Sister Funke Adeyemi",
        "notes": "Lives around GRA and asked for weekday follow-up.",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "record_id": "rec-002",
        "record_type": "convert",
        "name": "Peter Chukwudi",
        "phone": "+234 803 222 1002",
        "gender": "Male",
        "location": "University DLBC",
        "status": "contacted",
        "date": "2026-03-22",
        "service": "Sunday Worship Service",
        "assigned_to": "Brother Kehinde Bello",
        "notes": "Follow-up call completed and hostel visit planned.",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "record_id": "rec-003",
        "record_type": "newcomer",
        "name": "Sarah Afolabi",
        "phone": "+234 803 222 1003",
        "gender": "Female",
        "location": "Tanke DLBC",
        "status": "integrated",
        "date": "2026-03-17",
        "service": "Monday Bible Study",
        "assigned_to": "Sister Esther Bamidele",
        "notes": "Now attending workers' preparation class.",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
    },
]

BASE_ATTENDANCE = [
    {
        "attendance_id": "att-001",
        "worker_id": "wrk-001",
        "worker_name": "Adebayo Oluwaseun",
        "unit": "Ushering",
        "status": "present",
        "event_title": "Sunday Worship Service",
        "date": "2026-03-22",
        "location": "GRA DLBC",
        "recorded_by": "Pastor Samuel Adebayo",
        "reason": "On duty from opening prayer.",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "attendance_id": "att-002",
        "worker_id": "wrk-002",
        "worker_name": "Fatima Hassan",
        "unit": "Choir",
        "status": "late",
        "event_title": "Sunday Worship Service",
        "date": "2026-03-22",
        "location": "GRA DLBC",
        "recorded_by": "Pastor Samuel Adebayo",
        "reason": "Joined after traffic delay.",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "attendance_id": "att-003",
        "worker_id": "wrk-004",
        "worker_name": "Blessing Ihejirika",
        "unit": "Prayer",
        "status": "present",
        "event_title": "Sunday Worship Service",
        "date": "2026-03-22",
        "location": "University DLBC",
        "recorded_by": "Pastor Deborah Yusuf",
        "reason": "Led opening prayer session.",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "attendance_id": "att-004",
        "worker_id": "wrk-005",
        "worker_name": "Michael Adesola",
        "unit": "Music",
        "status": "excused",
        "event_title": "Monday Bible Study",
        "date": "2026-03-17",
        "location": "Tanke DLBC",
        "recorded_by": "Pastor David Akinwale",
        "reason": "Travelled for approved family emergency.",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
    },
]

BASE_REQUESTS = [
    {
        "request_id": "req-001",
        "request_type": "transfer_request",
        "worker_name": "Michael Adesola",
        "worker_id": "wrk-005",
        "origin_location": "Tanke DLBC",
        "destination_location": "University DLBC",
        "requested_by": "Pastor Samuel Adebayo",
        "status": "pending",
        "submitted_at": "2026-03-22 07:15",
        "current_stage": "Waiting for origin approval",
        "summary": "Worker is moving from Tanke DLBC to University DLBC and needs pastoral release.",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
        "timeline": [
            {"label": "Submitted", "state": "done", "note": "Request entered by local pastor."},
            {"label": "Origin review", "state": "current", "note": "Awaiting origin branch review."},
            {"label": "Destination review", "state": "pending", "note": "Next level after release."},
        ],
        "review_history": [],
    },
    {
        "request_id": "req-002",
        "request_type": "status_change",
        "worker_name": "Isaac Abiodun",
        "worker_id": "wrk-007",
        "origin_location": "Offa Township DLBC",
        "destination_location": "",
        "requested_by": "Pastor Deborah Yusuf",
        "status": "escalated",
        "submitted_at": "2026-03-21 18:10",
        "current_stage": "Region review",
        "summary": "Local branch requested a change from inactive to active after the worker resumed attendance.",
        "path": LOCATION_LOOKUP["Offa Township DLBC"]["path"],
        "timeline": [
            {"label": "Submitted", "state": "done", "note": "Status restoration request submitted."},
            {"label": "Location review", "state": "done", "note": "Local review completed."},
            {"label": "Region review", "state": "current", "note": "Escalated upward for final decision."},
        ],
        "review_history": [
            {"reviewer": "Pastor Samuel Adebayo", "action": "escalated", "note": "Needs wider oversight before approval.", "time": "Yesterday"},
        ],
    },
    {
        "request_id": "req-003",
        "request_type": "removal_request",
        "worker_name": "Emmanuel Okafor",
        "worker_id": "wrk-003",
        "origin_location": "GRA DLBC",
        "destination_location": "",
        "requested_by": "Pastor Samuel Adebayo",
        "status": "pending",
        "submitted_at": "2026-03-22 08:40",
        "current_stage": "Group pastor review",
        "summary": "Removal request raised because the worker has relocated and has been inactive for six weeks.",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
        "timeline": [
            {"label": "Submitted", "state": "done", "note": "Removal request created."},
            {"label": "Group review", "state": "current", "note": "Waiting for next level decision."},
            {"label": "Final decision", "state": "pending", "note": "Will close after approval or rejection."},
        ],
        "review_history": [],
    },
    {
        "request_id": "req-004",
        "request_type": "transfer_request",
        "worker_name": "Blessing Ihejirika",
        "worker_id": "wrk-004",
        "origin_location": "University DLBC",
        "destination_location": "GRA DLBC",
        "requested_by": "Pastor Deborah Yusuf",
        "status": "approved",
        "submitted_at": "2026-03-19 11:30",
        "current_stage": "Approved",
        "summary": "Short-term transfer completed for choir support during combined meetings.",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
        "timeline": [
            {"label": "Submitted", "state": "done", "note": "Transfer request created."},
            {"label": "Review", "state": "done", "note": "Reviewed by group pastor."},
            {"label": "Approved", "state": "done", "note": "Transfer approved."},
        ],
        "review_history": [
            {"reviewer": "Pastor David Akinwale", "action": "approved", "note": "Approved for one combined service cycle.", "time": "2 days ago"},
        ],
    },
]

BASE_INBOX = [
    {
        "item_id": "inbox-001",
        "kind": "worker_registration",
        "title": "Approve worker registration",
        "subject": "Emmanuel Okafor",
        "worker_id": "wrk-003",
        "location": "GRA DLBC",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
        "submitted_at": "20 mins ago",
        "priority": "High",
        "current_stage": "Waiting for location review",
        "summary": "Media unit worker registration is pending verification before account creation.",
        "resolved": False,
    },
    {
        "item_id": "inbox-002",
        "kind": "user_approval",
        "title": "Approve app access",
        "subject": "Esther Bamidele",
        "account_id": "usr-003",
        "worker_id": "wrk-009",
        "location": "GRA DLBC",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
        "submitted_at": "45 mins ago",
        "priority": "Medium",
        "current_stage": "Waiting for location review",
        "summary": "Worker has requested mobile access to submit local attendance and count records.",
        "resolved": False,
    },
    {
        "item_id": "inbox-003",
        "kind": "removal_request",
        "title": "Review worker removal request",
        "subject": "Emmanuel Okafor",
        "request_id": "req-003",
        "worker_id": "wrk-003",
        "location": "GRA DLBC",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
        "submitted_at": "2 hours ago",
        "priority": "High",
        "current_stage": "Group pastor review",
        "summary": "Removal request raised because the worker has relocated and has been inactive for six weeks.",
        "resolved": False,
    },
    {
        "item_id": "inbox-004",
        "kind": "transfer_request",
        "title": "Review transfer request",
        "subject": "Michael Adesola",
        "request_id": "req-001",
        "worker_id": "wrk-005",
        "location": "Tanke DLBC",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
        "submitted_at": "Today, 07:15",
        "priority": "Medium",
        "current_stage": "Waiting for origin approval",
        "summary": "Worker is moving from Tanke DLBC to University DLBC and needs pastoral release.",
        "resolved": False,
    },
    {
        "item_id": "inbox-005",
        "kind": "status_change",
        "title": "Review status change",
        "subject": "Isaac Abiodun",
        "request_id": "req-002",
        "worker_id": "wrk-007",
        "location": "Offa Township DLBC",
        "path": LOCATION_LOOKUP["Offa Township DLBC"]["path"],
        "submitted_at": "Yesterday",
        "priority": "Low",
        "current_stage": "Region review",
        "summary": "Local branch requested a change from inactive to active after the worker resumed attendance.",
        "resolved": False,
    },
]

BASE_ACTIVITY = [
    {
        "message": "Sunday count submitted for GRA DLBC",
        "meta": "Brother Adebayo Oluwaseun | 12 mins ago",
        "tone": "success",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "message": "App access request received from Esther Bamidele",
        "meta": "GRA DLBC | 45 mins ago",
        "tone": "warning",
        "path": LOCATION_LOOKUP["GRA DLBC"]["path"],
    },
    {
        "message": "Transfer request raised for Michael Adesola",
        "meta": "Tanke DLBC | Today, 07:15",
        "tone": "info",
        "path": LOCATION_LOOKUP["Tanke DLBC"]["path"],
    },
    {
        "message": "Worker registration approved for Blessing Ihejirika",
        "meta": "University DLBC | Yesterday",
        "tone": "success",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "message": "Offa Township DLBC is yet to submit Bible study count",
        "meta": "Offa Region | Yesterday",
        "tone": "danger",
        "path": LOCATION_LOOKUP["Offa Township DLBC"]["path"],
    },
]


BASE_ANNOUNCEMENTS = [
    {
        "announcement_id": "ann-001",
        "title": "Thursday workers meeting reminder",
        "meeting": "workers_meeting",
        "meeting_label": "Workers Meeting",
        "meeting_date": "2026-03-26",
        "audience": "All workers",
        "status": "published",
        "summary": "Unit leaders should remind workers to come with updated attendance and follow-up notes.",
        "body": "Please remind all workers that Thursday workers meeting will start by 5:00 PM. Unit leaders should come with their latest attendance and follow-up notes so decisions can be taken quickly.",
        "items": [
            "Attendance and absence reasons should be complete before the meeting.",
            "New worker access requests should be reviewed before closing.",
            "Choir and media units should confirm Sunday readiness.",
        ],
        "created_by": "Pastor David Akinwale",
        "updated_at": "2026-03-20 18:10",
        "published_at": "2026-03-20 18:30",
        "path": SCOPE_PATHS["region"]["Ilorin North Region"],
    },
    {
        "announcement_id": "ann-002",
        "title": "Sunday follow-up team arrangement",
        "meeting": "sunday_service",
        "meeting_label": "Sunday Service",
        "meeting_date": "2026-03-22",
        "audience": "Follow-up workers",
        "status": "draft",
        "summary": "A shorter Sunday plan is being prepared for all follow-up workers after the service.",
        "body": "A short follow-up arrangement is being prepared for all workers assigned to welcome newcomers after service. This draft is waiting for final review before it is shared.",
        "items": [
            "First-time worshippers should be greeted before dispersal.",
            "Assigned workers should collect clear phone numbers for follow-up.",
        ],
        "created_by": "Pastor Deborah Yusuf",
        "updated_at": "2026-03-21 09:15",
        "published_at": "",
        "path": SCOPE_PATHS["group"]["Ilorin East Group"],
    },
    {
        "announcement_id": "ann-003",
        "title": "Special outreach movement plan",
        "meeting": "special_notice",
        "meeting_label": "Special Notice",
        "meeting_date": "2026-03-28",
        "audience": "All locations",
        "status": "published",
        "summary": "Locations under Kwara State should confirm transport, publicity, and assigned follow-up brethren.",
        "body": "The state outreach movement holds on Saturday, March 28, 2026. All locations should confirm transport plans, publicity readiness, and assigned follow-up brethren before Wednesday evening.",
        "items": [
            "Each group should submit its movement contact person.",
            "Treasury teams should prepare simple accountability sheets.",
            "Follow-up names from the field should be returned the same day.",
        ],
        "created_by": "Pastor Grace Omoniyi",
        "updated_at": "2026-03-19 14:40",
        "published_at": "2026-03-19 15:00",
        "path": SCOPE_PATHS["state"]["Kwara State"],
    },
    {
        "announcement_id": "ann-004",
        "title": "Campus fellowship media request",
        "meeting": "leaders_briefing",
        "meeting_label": "Leaders Briefing",
        "meeting_date": "2026-03-24",
        "audience": "Campus leaders",
        "status": "archived",
        "summary": "The last media request note has been archived after distribution.",
        "body": "The previous campus fellowship media request note has been archived because all requested materials were already distributed and acknowledged.",
        "items": [
            "Old poster files should not be reused.",
            "Fresh meeting artwork has already been approved.",
        ],
        "created_by": "Pastor Deborah Yusuf",
        "updated_at": "2026-03-18 08:20",
        "published_at": "2026-03-17 11:00",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
]


BASE_MEDIA_GALLERIES = [
    {
        "gallery_id": "gal-001",
        "title": "Workers Meeting Highlights",
        "event_name": "Thursday Workers Meeting",
        "event_date": "2026-03-20",
        "visibility": "scope_only",
        "description": "Short photo set for attendance review, unit coordination, and quick follow-up reference.",
        "scope_label": "Ilorin North Region",
        "created_by": "Pastor David Akinwale",
        "updated_at": "2026-03-20 19:10",
        "path": SCOPE_PATHS["region"]["Ilorin North Region"],
    },
    {
        "gallery_id": "gal-002",
        "title": "University Outreach Follow-up",
        "event_name": "Campus Outreach",
        "event_date": "2026-03-21",
        "visibility": "private_review",
        "description": "Items kept for follow-up workers while contact and testimony notes are still being checked.",
        "scope_label": "University DLBC",
        "created_by": "Pastor Deborah Yusuf",
        "updated_at": "2026-03-21 18:25",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "gallery_id": "gal-003",
        "title": "State Outreach Publicity Pack",
        "event_name": "Kwara State Outreach",
        "event_date": "2026-03-18",
        "visibility": "national_share",
        "description": "Approved media pack for publicity, reports, and upward sharing after the outreach briefing.",
        "scope_label": "Kwara State",
        "created_by": "Pastor Grace Omoniyi",
        "updated_at": "2026-03-18 15:40",
        "path": SCOPE_PATHS["state"]["Kwara State"],
    },
]


BASE_MEDIA_ITEMS = [
    {
        "item_id": "med-001",
        "gallery_id": "gal-001",
        "title": "Opening prayer session",
        "media_type": "photo",
        "caption": "Prayer coordinators praying with workers before the meeting started.",
        "file_label": "workers_meeting_opening.jpg",
        "duration": "",
        "uploaded_by": "Brother Adebayo Oluwaseun",
        "uploaded_at": "2026-03-20 18:12",
        "path": SCOPE_PATHS["region"]["Ilorin North Region"],
    },
    {
        "item_id": "med-002",
        "gallery_id": "gal-001",
        "title": "Attendance review clip",
        "media_type": "video",
        "caption": "Short clip showing the attendance review and unit reminders.",
        "file_label": "workers_attendance_review.mp4",
        "duration": "01:24",
        "uploaded_by": "Brother Adebayo Oluwaseun",
        "uploaded_at": "2026-03-20 18:34",
        "path": SCOPE_PATHS["region"]["Ilorin North Region"],
    },
    {
        "item_id": "med-003",
        "gallery_id": "gal-002",
        "title": "Campus welcome stand",
        "media_type": "photo",
        "caption": "Welcome stand used to receive first-time worshippers after the outreach.",
        "file_label": "campus_welcome_stand.jpg",
        "duration": "",
        "uploaded_by": "Sister Esther Bamidele",
        "uploaded_at": "2026-03-21 17:05",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "item_id": "med-004",
        "gallery_id": "gal-002",
        "title": "Decision prayer moment",
        "media_type": "photo",
        "caption": "Prayer session with converts after the outreach message.",
        "file_label": "campus_decision_prayer.jpg",
        "duration": "",
        "uploaded_by": "Sister Esther Bamidele",
        "uploaded_at": "2026-03-21 17:42",
        "path": LOCATION_LOOKUP["University DLBC"]["path"],
    },
    {
        "item_id": "med-005",
        "gallery_id": "gal-003",
        "title": "Publicity artwork review",
        "media_type": "photo",
        "caption": "Approved artwork shown during the state outreach review meeting.",
        "file_label": "state_publicity_artwork.jpg",
        "duration": "",
        "uploaded_by": "Pastor Grace Omoniyi",
        "uploaded_at": "2026-03-18 14:50",
        "path": SCOPE_PATHS["state"]["Kwara State"],
    },
    {
        "item_id": "med-006",
        "gallery_id": "gal-003",
        "title": "Outreach briefing clip",
        "media_type": "video",
        "caption": "Brief message clip explaining movement, follow-up, and accountability plans.",
        "file_label": "state_outreach_briefing.mp4",
        "duration": "02:08",
        "uploaded_by": "Pastor Grace Omoniyi",
        "uploaded_at": "2026-03-18 15:22",
        "path": SCOPE_PATHS["state"]["Kwara State"],
    },
]


BASE_SYSTEM_NOTIFICATIONS = [
    {
        "notification_id": "sysn-001",
        "title": "New app version awaiting rollout",
        "body": "Android 1.2.4 is ready for final confirmation before public release.",
        "kind": "release",
        "priority": "high",
        "status": "unread",
        "time": "2026-03-22 08:10",
        "path": SCOPE_PATHS["nation"]["Nigeria"],
    },
    {
        "notification_id": "sysn-002",
        "title": "Audit export completed",
        "body": "The latest audit extract for national review is now ready.",
        "kind": "audit",
        "priority": "medium",
        "status": "read",
        "time": "2026-03-21 17:20",
        "path": SCOPE_PATHS["nation"]["Nigeria"],
    },
    {
        "notification_id": "sysn-003",
        "title": "Database latency returned to normal",
        "body": "The short latency spike seen yesterday is no longer affecting requests.",
        "kind": "health",
        "priority": "low",
        "status": "read",
        "time": "2026-03-21 09:45",
        "path": "global",
    },
    {
        "notification_id": "sysn-004",
        "title": "Permission review recommended",
        "body": "One global role has gained access to a new permission family and should be reviewed.",
        "kind": "rbac",
        "priority": "medium",
        "status": "unread",
        "time": "2026-03-20 16:10",
        "path": "global",
    },
]


BASE_APP_VERSIONS = [
    {
        "version_id": "ver-001",
        "app_name": "DCLM Admin",
        "platform": "Android",
        "version_number": "1.2.3",
        "min_os_version": "8.0",
        "release_date": "2026-03-10",
        "status": "active",
        "force_update": "No",
        "notes": "Current stable production build.",
    },
    {
        "version_id": "ver-002",
        "app_name": "DCLM Admin",
        "platform": "Android",
        "version_number": "1.2.4",
        "min_os_version": "8.0",
        "release_date": "2026-03-22",
        "status": "draft",
        "force_update": "No",
        "notes": "Minor fix release for notifications and report loading.",
    },
    {
        "version_id": "ver-003",
        "app_name": "DCLM Admin",
        "platform": "iOS",
        "version_number": "1.1.9",
        "min_os_version": "14.0",
        "release_date": "2026-03-05",
        "status": "active",
        "force_update": "Yes",
        "notes": "Security update with forced upgrade.",
    },
]


BASE_AUDIT_LOGS = [
    {
        "log_id": "aud-001",
        "time": "2026-03-22 07:55",
        "actor": "Pastor John Fasanmi",
        "action": "Published weekly communication",
        "target": "National workers briefing",
        "status": "success",
        "scope_label": "Nigeria",
        "path": SCOPE_PATHS["nation"]["Nigeria"],
    },
    {
        "log_id": "aud-002",
        "time": "2026-03-21 19:10",
        "actor": "Pastor Grace Omoniyi",
        "action": "Approved app user role update",
        "target": "Kwara State oversight team",
        "status": "success",
        "scope_label": "Kwara State",
        "path": SCOPE_PATHS["state"]["Kwara State"],
    },
    {
        "log_id": "aud-003",
        "time": "2026-03-21 13:40",
        "actor": "Pastor Michael Ojo",
        "action": "Ran seed utility",
        "target": "Program domain sync",
        "status": "warning",
        "scope_label": "Global",
        "path": "global",
    },
    {
        "log_id": "aud-004",
        "time": "2026-03-20 10:15",
        "actor": "Pastor Ruth Balogun",
        "action": "Viewed audit export",
        "target": "West Africa review pack",
        "status": "info",
        "scope_label": "West Africa Division",
        "path": SCOPE_PATHS["continent"]["West Africa Division"],
    },
]


BASE_RBAC_ROLES = [
    {
        "role_id": "role-001",
        "name": "Location Pastor",
        "level": 3,
        "permission_count": 3,
        "status": "active",
        "scope": "location",
        "description": "Handles day-to-day local administration with a simple action-first view.",
        "permission_ids": ["perm-001", "perm-003", "perm-008"],
    },
    {
        "role_id": "role-002",
        "name": "Group Pastor",
        "level": 4,
        "permission_count": 4,
        "status": "active",
        "scope": "group",
        "description": "Oversees group-level reviews, workers, and follow-up operations.",
        "permission_ids": ["perm-001", "perm-003", "perm-008", "perm-013"],
    },
    {
        "role_id": "role-003",
        "name": "Region Pastor",
        "level": 5,
        "permission_count": 7,
        "status": "active",
        "scope": "region+",
        "description": "Leads region operations including weekly communication and media oversight.",
        "permission_ids": ["perm-001", "perm-002", "perm-003", "perm-004", "perm-005", "perm-008", "perm-013"],
    },
    {
        "role_id": "role-004",
        "name": "State Overseer",
        "level": 6,
        "permission_count": 8,
        "status": "active",
        "scope": "state+",
        "description": "Combines oversight, reporting, and escalated operations at state level.",
        "permission_ids": ["perm-001", "perm-002", "perm-003", "perm-004", "perm-005", "perm-008", "perm-009", "perm-013"],
    },
    {
        "role_id": "role-005",
        "name": "National Admin",
        "level": 7,
        "permission_count": 11,
        "status": "active",
        "scope": "national+",
        "description": "Reviews governance alerts, releases, and audit visibility for the nation.",
        "permission_ids": ["perm-001", "perm-002", "perm-003", "perm-004", "perm-005", "perm-008", "perm-009", "perm-010", "perm-011", "perm-013", "perm-014"],
    },
    {
        "role_id": "role-006",
        "name": "Global Admin",
        "level": 9,
        "permission_count": 14,
        "status": "active",
        "scope": "global",
        "description": "Holds the widest governance access including RBAC management and seed utilities.",
        "permission_ids": [
            "perm-001",
            "perm-002",
            "perm-003",
            "perm-004",
            "perm-005",
            "perm-006",
            "perm-007",
            "perm-008",
            "perm-009",
            "perm-010",
            "perm-011",
            "perm-012",
            "perm-013",
            "perm-014",
        ],
    },
]


BASE_RBAC_PERMISSIONS = [
    {"permission_id": "perm-001", "family": "announcements", "key": "announcements:read", "scope": "region+"},
    {"permission_id": "perm-002", "family": "announcements", "key": "announcements:manage", "scope": "region+"},
    {"permission_id": "perm-003", "family": "media", "key": "media:read", "scope": "region+"},
    {"permission_id": "perm-004", "family": "media", "key": "media:create_gallery", "scope": "region+"},
    {"permission_id": "perm-005", "family": "media", "key": "media:create_item", "scope": "region+"},
    {"permission_id": "perm-006", "family": "media", "key": "media:delete_gallery", "scope": "region+"},
    {"permission_id": "perm-007", "family": "media", "key": "media:delete_item", "scope": "region+"},
    {"permission_id": "perm-008", "family": "reports", "key": "reports:read", "scope": "state+"},
    {"permission_id": "perm-009", "family": "reports", "key": "reports:refresh", "scope": "national+"},
    {"permission_id": "perm-010", "family": "notifications", "key": "notifications:read", "scope": "national+"},
    {"permission_id": "perm-011", "family": "system", "key": "system:read_audit_logs", "scope": "national+"},
    {"permission_id": "perm-012", "family": "system", "key": "system:seed", "scope": "global"},
    {"permission_id": "perm-013", "family": "rbac", "key": "rbac:read", "scope": "national+"},
    {"permission_id": "perm-014", "family": "rbac", "key": "rbac:manage", "scope": "global"},
]


BASE_SYSTEM_HEALTH = {
    "status": "healthy",
    "api_latency_ms": 186,
    "background_jobs": 4,
    "queue_wait_seconds": 11,
    "db_connections": 18,
    "services": [
        {"name": "API", "status": "healthy", "note": "Request times remain within expected range."},
        {"name": "Database", "status": "healthy", "note": "Read and write checks passed."},
        {"name": "Notifications", "status": "warning", "note": "A small delivery backlog is being cleared."},
        {"name": "Report refresh", "status": "healthy", "note": "Scheduled refresh completed overnight."},
    ],
}


NOTIFICATIONS = [
    {
        "title": "Three requests need your attention",
        "body": "Open the inbox to review worker and user approvals for your scope.",
        "time": "Just now",
    },
    {
        "title": "Sunday count reminder",
        "body": "Counts are still pending in one branch under Ilorin East Group.",
        "time": "15 mins ago",
    },
]

UNITS = ["Ushering", "Choir", "Media", "Prayer", "Music", "Children", "Welfare", "Evangelism"]


def in_scope(path: str, scope_path: str) -> bool:
    return path == scope_path or path.startswith(f"{scope_path}.")


def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (item.get("location", ""), item.get("name", item.get("event_title", "")))


class DemoStore:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.program_domains = deepcopy(BASE_PROGRAM_DOMAINS)
        self.program_types = deepcopy(BASE_PROGRAM_TYPES)
        self.program_events = deepcopy(BASE_PROGRAM_EVENTS)
        self.workers = deepcopy(BASE_WORKERS)
        self.users = deepcopy(BASE_USERS)
        self.official_appointments = deepcopy(BASE_OFFICIAL_APPOINTMENTS)
        self.fellowships = deepcopy(BASE_FELLOWSHIPS)
        self.location_profiles = deepcopy(BASE_LOCATION_PROFILES)
        self.church_members = deepcopy(BASE_CHURCH_MEMBERS)
        self.fellowship_attendance = deepcopy(BASE_FELLOWSHIP_ATTENDANCE)
        self.fellowship_offerings = deepcopy(BASE_FELLOWSHIP_OFFERINGS)
        self.fellowship_testimonies = deepcopy(BASE_FELLOWSHIP_TESTIMONIES)
        self.fellowship_prayers = deepcopy(BASE_FELLOWSHIP_PRAYERS)
        self.fellowship_summaries = deepcopy(BASE_FELLOWSHIP_SUMMARIES)
        self.counts = deepcopy(BASE_COUNTS)
        self.finance = deepcopy(BASE_FINANCE)
        self.records = deepcopy(BASE_RECORDS)
        self.attendance = deepcopy(BASE_ATTENDANCE)
        self.requests = deepcopy(BASE_REQUESTS)
        self.announcements = deepcopy(BASE_ANNOUNCEMENTS)
        self.media_galleries = deepcopy(BASE_MEDIA_GALLERIES)
        self.media_items = deepcopy(BASE_MEDIA_ITEMS)
        self.system_notifications = deepcopy(BASE_SYSTEM_NOTIFICATIONS)
        self.app_versions = deepcopy(BASE_APP_VERSIONS)
        self.audit_logs = deepcopy(BASE_AUDIT_LOGS)
        self.rbac_roles = deepcopy(BASE_RBAC_ROLES)
        self.rbac_permissions = deepcopy(BASE_RBAC_PERMISSIONS)
        self.system_health = deepcopy(BASE_SYSTEM_HEALTH)
        self.inbox = deepcopy(BASE_INBOX)
        self.activity = deepcopy(BASE_ACTIVITY)

    def visible_locations(self, scope_path: str) -> list[dict[str, Any]]:
        return [row for row in LOCATIONS if in_scope(row["path"], scope_path)]

    def list_location_profiles(
        self,
        scope_path: str,
        *,
        search: str = "",
        status: str = "",
        church_type: str = "",
    ) -> list[dict[str, Any]]:
        rows = [row for row in self.location_profiles if in_scope(row["path"], scope_path)]
        if status:
            rows = [row for row in rows if row["status"] == status]
        if church_type:
            rows = [row for row in rows if row["church_type"] == church_type]
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["location"].lower()
                or term in row["address"].lower()
                or term in row["pastor_name"].lower()
                or term in row["group"].lower()
                or term in row["region"].lower()
            ]
        result = []
        for row in rows:
            result.append({**row, **self.location_profile_summary(row["location_key"])})
        return sorted(result, key=lambda row: (row["state"], row["region"], row["location"]))

    def get_location_profile(self, location_key: str) -> dict[str, Any] | None:
        return next((row for row in self.location_profiles if row["location_key"] == location_key), None)

    def location_profile_summary(self, location_key: str) -> dict[str, Any]:
        profile = self.get_location_profile(location_key)
        if profile is None:
            return {
                "worker_count": 0,
                "user_count": 0,
                "member_count": 0,
                "fellowship_count": 0,
                "pending_inbox": 0,
                "latest_count": 0,
            }
        path = profile["path"]
        workers = self.list_workers(path)
        users = self.list_users(path)
        members = self.list_church_members(path)
        fellowships = self.list_fellowships(path)
        inbox = self.list_inbox(path)
        counts = self.list_counts(path)
        return {
            "worker_count": len(workers),
            "user_count": len(users),
            "member_count": len(members),
            "fellowship_count": len(fellowships),
            "pending_inbox": len(inbox),
            "latest_count": counts[0]["total"] if counts else 0,
        }

    def update_location_profile(self, location_key: str, payload: dict[str, str]) -> dict[str, Any] | None:
        profile = self.get_location_profile(location_key)
        if profile is None:
            return None
        for field in ["address", "pastor_name", "assistant_name", "phone", "church_type", "status"]:
            value = payload.get(field)
            if value is not None:
                profile[field] = value.strip()
        self.activity.insert(
            0,
            {
                "message": f"Location profile updated for {profile['location']}",
                "meta": f"{profile['region']} - Just now",
                "tone": "info",
                "path": profile["path"],
            },
        )
        return profile

    def list_announcements(
        self,
        scope_path: str,
        *,
        search: str = "",
        status: str = "",
        meeting: str = "",
    ) -> list[dict[str, Any]]:
        rows = [row for row in self.announcements if in_scope(row["path"], scope_path)]
        if status and status != "all":
            rows = [row for row in rows if row["status"] == status]
        if meeting:
            rows = [row for row in rows if row["meeting"] == meeting]
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["title"].lower()
                or term in row["summary"].lower()
                or term in row["audience"].lower()
                or term in row["meeting_label"].lower()
            ]
        return sorted(rows, key=lambda row: (row["meeting_date"], row["updated_at"]), reverse=True)

    def get_announcement(self, announcement_id: str) -> dict[str, Any] | None:
        return next((row for row in self.announcements if row["announcement_id"] == announcement_id), None)

    def announcement_summary(self, scope_path: str) -> dict[str, int]:
        rows = self.list_announcements(scope_path)
        return {
            "total": len(rows),
            "published": sum(1 for row in rows if row["status"] == "published"),
            "drafts": sum(1 for row in rows if row["status"] == "draft"),
            "archived": sum(1 for row in rows if row["status"] == "archived"),
        }

    def add_announcement(
        self,
        payload: dict[str, str],
        *,
        scope_path: str,
        author_name: str,
    ) -> dict[str, Any]:
        next_index = len(self.announcements) + 1
        action = payload.get("submit_action", "draft")
        meeting_labels = {
            "workers_meeting": "Workers Meeting",
            "leaders_briefing": "Leaders Briefing",
            "sunday_service": "Sunday Service",
            "special_notice": "Special Notice",
        }
        items = [
            payload.get(f"item_{index}", "").strip()
            for index in range(1, 9)
            if payload.get(f"item_{index}", "").strip()
        ]
        row = {
            "announcement_id": f"ann-{next_index:03d}",
            "title": payload["title"].strip(),
            "meeting": payload["meeting"],
            "meeting_label": meeting_labels.get(payload["meeting"], payload["meeting"].replace("_", " ").title()),
            "meeting_date": payload["meeting_date"],
            "audience": payload["audience"].strip(),
            "status": "published" if action == "publish" else "draft",
            "summary": payload["summary"].strip(),
            "body": payload["body"].strip(),
            "items": items,
            "created_by": author_name,
            "updated_at": f"{TODAY.isoformat()} 10:00",
            "published_at": f"{TODAY.isoformat()} 10:05" if action == "publish" else "",
            "path": scope_path,
        }
        self.announcements.insert(0, row)
        self.activity.insert(
            0,
            {
                "message": f"Communication saved: {row['title']}",
                "meta": f"{author_name} - Just now",
                "tone": "success" if row["status"] == "published" else "info",
                "path": scope_path,
            },
        )
        return row

    def update_announcement(
        self,
        announcement_id: str,
        payload: dict[str, str],
        *,
        actor_name: str,
    ) -> dict[str, Any] | None:
        row = self.get_announcement(announcement_id)
        if row is None:
            return None
        action = payload.get("submit_action", "draft")
        meeting_labels = {
            "workers_meeting": "Workers Meeting",
            "leaders_briefing": "Leaders Briefing",
            "sunday_service": "Sunday Service",
            "special_notice": "Special Notice",
        }
        row["title"] = payload["title"].strip()
        row["meeting"] = payload["meeting"]
        row["meeting_label"] = meeting_labels.get(payload["meeting"], payload["meeting"].replace("_", " ").title())
        row["meeting_date"] = payload["meeting_date"]
        row["audience"] = payload["audience"].strip()
        row["summary"] = payload["summary"].strip()
        row["body"] = payload["body"].strip()
        row["items"] = [
            payload.get(f"item_{index}", "").strip()
            for index in range(1, 9)
            if payload.get(f"item_{index}", "").strip()
        ]
        row["status"] = "published" if action == "publish" else "draft"
        row["updated_at"] = f"{TODAY.isoformat()} 10:20"
        if action == "publish":
            row["published_at"] = f"{TODAY.isoformat()} 10:20"
        self.activity.insert(
            0,
            {
                "message": f"Communication updated: {row['title']}",
                "meta": f"{actor_name} - Just now",
                "tone": "success" if action == "publish" else "info",
                "path": row["path"],
            },
        )
        return row

    def set_announcement_status(
        self,
        announcement_id: str,
        *,
        action: str,
        actor_name: str,
        note: str = "",
    ) -> dict[str, Any] | None:
        row = self.get_announcement(announcement_id)
        if row is None:
            return None
        action_map = {
            "publish": ("published", "Communication published"),
            "archive": ("archived", "Communication archived"),
            "draft": ("draft", "Communication returned to draft"),
        }
        if action not in action_map:
            return None
        status, activity_message = action_map[action]
        row["status"] = status
        row["updated_at"] = f"{TODAY.isoformat()} 10:35"
        if action == "publish":
            row["published_at"] = f"{TODAY.isoformat()} 10:35"
        self.activity.insert(
            0,
            {
                "message": f"{activity_message}: {row['title']}",
                "meta": f"{actor_name} - Just now",
                "tone": "success" if action == "publish" else "warning" if action == "archive" else "info",
                "path": row["path"],
            },
        )
        self.audit_logs.insert(
            0,
            {
                "log_id": f"aud-{len(self.audit_logs) + 1:03d}",
                "time": f"{TODAY.isoformat()} 10:35",
                "actor": actor_name,
                "action": activity_message,
                "target": row["title"],
                "status": "success",
                "scope_label": row["path"].split(".")[-1].replace("_", " ").title(),
                "path": row["path"],
            },
        )
        if note.strip():
            row["body"] = f"{row['body']}\n\nRecord note: {note.strip()}"
        return row

    def list_media_galleries(
        self,
        scope_path: str,
        *,
        search: str = "",
        visibility: str = "",
    ) -> list[dict[str, Any]]:
        rows = [row for row in self.media_galleries if in_scope(row["path"], scope_path)]
        if visibility and visibility != "all":
            rows = [row for row in rows if row["visibility"] == visibility]
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["title"].lower()
                or term in row["event_name"].lower()
                or term in row["description"].lower()
                or term in row["scope_label"].lower()
            ]
        result = []
        for row in rows:
            items = [item for item in self.media_items if item["gallery_id"] == row["gallery_id"]]
            result.append(
                {
                    **row,
                    "item_count": len(items),
                    "photo_count": sum(1 for item in items if item["media_type"] == "photo"),
                    "video_count": sum(1 for item in items if item["media_type"] == "video"),
                    "latest_upload": max((item["uploaded_at"] for item in items), default=row["updated_at"]),
                }
            )
        return sorted(result, key=lambda row: (row["event_date"], row["latest_upload"]), reverse=True)

    def get_media_gallery(self, gallery_id: str) -> dict[str, Any] | None:
        gallery = next((row for row in self.media_galleries if row["gallery_id"] == gallery_id), None)
        if gallery is None:
            return None
        items = [item for item in self.media_items if item["gallery_id"] == gallery_id]
        return {
            **gallery,
            "item_count": len(items),
            "photo_count": sum(1 for item in items if item["media_type"] == "photo"),
            "video_count": sum(1 for item in items if item["media_type"] == "video"),
        }

    def media_gallery_summary(self, scope_path: str) -> dict[str, int]:
        galleries = self.list_media_galleries(scope_path)
        items = self.list_media_items(scope_path)
        return {
            "galleries": len(galleries),
            "items": len(items),
            "videos": sum(1 for item in items if item["media_type"] == "video"),
            "shared_upward": sum(1 for gallery in galleries if gallery["visibility"] == "national_share"),
        }

    def add_media_gallery(
        self,
        payload: dict[str, str],
        *,
        scope_path: str,
        scope_label: str,
        actor_name: str,
    ) -> dict[str, Any]:
        next_index = len(self.media_galleries) + 1
        row = {
            "gallery_id": f"gal-{next_index:03d}",
            "title": payload["title"].strip(),
            "event_name": payload["event_name"].strip(),
            "event_date": payload["event_date"],
            "visibility": payload["visibility"],
            "description": payload.get("description", "").strip(),
            "scope_label": scope_label,
            "created_by": actor_name,
            "updated_at": f"{TODAY.isoformat()} 11:05",
            "path": scope_path,
        }
        self.media_galleries.insert(0, row)
        self.activity.insert(
            0,
            {
                "message": f"Media gallery created: {row['title']}",
                "meta": f"{actor_name} - Just now",
                "tone": "info",
                "path": scope_path,
            },
        )
        return self.get_media_gallery(row["gallery_id"]) or row

    def list_media_items(
        self,
        scope_path: str,
        *,
        search: str = "",
        media_type: str = "",
        gallery_id: str = "",
    ) -> list[dict[str, Any]]:
        rows = [row for row in self.media_items if in_scope(row["path"], scope_path)]
        if gallery_id:
            rows = [row for row in rows if row["gallery_id"] == gallery_id]
        if media_type and media_type != "all":
            rows = [row for row in rows if row["media_type"] == media_type]
        if search:
            term = search.lower().strip()
            rows = [row for row in rows if term in row["title"].lower() or term in row["caption"].lower() or term in row["file_label"].lower()]

        galleries = {gallery["gallery_id"]: gallery for gallery in self.media_galleries}
        result = []
        for row in rows:
            gallery = galleries.get(row["gallery_id"])
            gallery_title = gallery["title"] if gallery else "Unknown gallery"
            result.append(
                {
                    **row,
                    "gallery_title": gallery_title,
                    "gallery_visibility": gallery["visibility"] if gallery else "",
                    "scope_label": gallery["scope_label"] if gallery else "",
                    "event_date": gallery["event_date"] if gallery else "",
                }
            )
        return sorted(result, key=lambda row: row["uploaded_at"], reverse=True)

    def get_media_item(self, item_id: str) -> dict[str, Any] | None:
        return next((row for row in self.media_items if row["item_id"] == item_id), None)

    def add_media_item(
        self,
        gallery_id: str,
        payload: dict[str, str],
        *,
        actor_name: str,
    ) -> dict[str, Any] | None:
        gallery = next((row for row in self.media_galleries if row["gallery_id"] == gallery_id), None)
        if gallery is None:
            return None
        next_index = len(self.media_items) + 1
        row = {
            "item_id": f"med-{next_index:03d}",
            "gallery_id": gallery_id,
            "title": payload["title"].strip(),
            "media_type": payload["media_type"],
            "caption": payload.get("caption", "").strip(),
            "file_label": payload["file_label"].strip(),
            "duration": payload.get("duration", "").strip(),
            "uploaded_by": actor_name,
            "uploaded_at": f"{TODAY.isoformat()} 11:20",
            "path": gallery["path"],
        }
        self.media_items.insert(0, row)
        gallery["updated_at"] = f"{TODAY.isoformat()} 11:20"
        self.activity.insert(
            0,
            {
                "message": f"Media item added to {gallery['title']}",
                "meta": f"{actor_name} - Just now",
                "tone": "success",
                "path": gallery["path"],
            },
        )
        item = self.get_media_item(row["item_id"])
        if item is None:
            return row
        return {
            **item,
            "gallery_title": gallery["title"],
            "gallery_visibility": gallery["visibility"],
            "scope_label": gallery["scope_label"],
            "event_date": gallery["event_date"],
        }

    def delete_media_gallery(self, gallery_id: str, *, actor_name: str) -> dict[str, Any] | None:
        gallery = next((row for row in self.media_galleries if row["gallery_id"] == gallery_id), None)
        if gallery is None:
            return None
        self.media_galleries = [row for row in self.media_galleries if row["gallery_id"] != gallery_id]
        self.media_items = [row for row in self.media_items if row["gallery_id"] != gallery_id]
        self.activity.insert(
            0,
            {
                "message": f"Media gallery removed: {gallery['title']}",
                "meta": f"{actor_name} - Just now",
                "tone": "warning",
                "path": gallery["path"],
            },
        )
        return gallery

    def delete_media_item(self, item_id: str, *, actor_name: str) -> dict[str, Any] | None:
        item = next((row for row in self.media_items if row["item_id"] == item_id), None)
        if item is None:
            return None
        self.media_items = [row for row in self.media_items if row["item_id"] != item_id]
        gallery = next((row for row in self.media_galleries if row["gallery_id"] == item["gallery_id"]), None)
        if gallery is not None:
            gallery["updated_at"] = f"{TODAY.isoformat()} 11:35"
        self.activity.insert(
            0,
            {
                "message": f"Media item removed: {item['title']}",
                "meta": f"{actor_name} - Just now",
                "tone": "warning",
                "path": item["path"],
            },
        )
        return item

    def list_system_notifications(
        self,
        scope_path: str,
        *,
        status: str = "",
        kind: str = "",
    ) -> list[dict[str, Any]]:
        rows = [row for row in self.system_notifications if in_scope(row["path"], scope_path)]
        if status and status != "all":
            rows = [row for row in rows if row["status"] == status]
        if kind and kind != "all":
            rows = [row for row in rows if row["kind"] == kind]
        return sorted(rows, key=lambda row: row["time"], reverse=True)

    def system_notification_summary(self, scope_path: str) -> dict[str, int]:
        rows = self.list_system_notifications(scope_path)
        return {
            "total": len(rows),
            "unread": sum(1 for row in rows if row["status"] == "unread"),
            "high_priority": sum(1 for row in rows if row["priority"] == "high"),
            "health_items": sum(1 for row in rows if row["kind"] == "health"),
        }

    def get_system_notification(self, notification_id: str) -> dict[str, Any] | None:
        return next((row for row in self.system_notifications if row["notification_id"] == notification_id), None)

    def set_system_notification_status(
        self,
        notification_id: str,
        *,
        status: str,
        actor_name: str,
    ) -> dict[str, Any] | None:
        row = self.get_system_notification(notification_id)
        if row is None or status not in {"read", "unread"}:
            return None
        row["status"] = status
        self.audit_logs.insert(
            0,
            {
                "log_id": f"aud-{len(self.audit_logs) + 1:03d}",
                "time": f"{TODAY.isoformat()} 10:45",
                "actor": actor_name,
                "action": "Updated notification status",
                "target": row["title"],
                "status": "success",
                "scope_label": "Global" if row["path"] == "global" else "Nigeria",
                "path": row["path"],
            },
        )
        return row

    def list_app_versions(self, *, platform: str = "", status: str = "") -> list[dict[str, Any]]:
        rows = self.app_versions
        if platform:
            rows = [row for row in rows if row["platform"] == platform]
        if status and status != "all":
            rows = [row for row in rows if row["status"] == status]
        return sorted(rows, key=lambda row: (row["release_date"], row["platform"]), reverse=True)

    def get_app_version(self, version_id: str) -> dict[str, Any] | None:
        return next((row for row in self.app_versions if row["version_id"] == version_id), None)

    def add_app_version(self, payload: dict[str, str], *, actor_name: str) -> dict[str, Any]:
        next_index = len(self.app_versions) + 1
        row = {
            "version_id": f"ver-{next_index:03d}",
            "app_name": payload["app_name"].strip(),
            "platform": payload["platform"],
            "version_number": payload["version_number"].strip(),
            "min_os_version": payload["min_os_version"].strip(),
            "release_date": payload["release_date"],
            "status": payload["status"],
            "force_update": payload["force_update"],
            "notes": payload.get("notes", "").strip(),
        }
        self.app_versions.insert(0, row)
        self.audit_logs.insert(
            0,
            {
                "log_id": f"aud-{len(self.audit_logs) + 1:03d}",
                "time": f"{TODAY.isoformat()} 10:40",
                "actor": actor_name,
                "action": "Created app version",
                "target": f"{row['platform']} {row['version_number']}",
                "status": "success",
                "scope_label": "Global",
                "path": "global",
            },
        )
        return row

    def activate_app_version(
        self,
        version_id: str,
        *,
        actor_name: str,
        force_update: str = "",
    ) -> dict[str, Any] | None:
        row = self.get_app_version(version_id)
        if row is None:
            return None
        for candidate in self.app_versions:
            if candidate["platform"] == row["platform"] and candidate["version_id"] != version_id and candidate["status"] == "active":
                candidate["status"] = "inactive"
        row["status"] = "active"
        if force_update in {"Yes", "No"}:
            row["force_update"] = force_update
        self.audit_logs.insert(
            0,
            {
                "log_id": f"aud-{len(self.audit_logs) + 1:03d}",
                "time": f"{TODAY.isoformat()} 10:47",
                "actor": actor_name,
                "action": "Activated app version",
                "target": f"{row['platform']} {row['version_number']}",
                "status": "success",
                "scope_label": "Global",
                "path": "global",
            },
        )
        self.system_notifications.insert(
            0,
            {
                "notification_id": f"sysn-{len(self.system_notifications) + 1:03d}",
                "title": f"{row['platform']} {row['version_number']} is now current",
                "body": "A new build has been marked as the active version for rollout tracking.",
                "kind": "release",
                "priority": "medium",
                "status": "unread",
                "time": f"{TODAY.isoformat()} 10:47",
                "path": "global",
            },
        )
        return row

    def get_system_health(self) -> dict[str, Any]:
        return self.system_health

    def list_audit_logs(
        self,
        scope_path: str,
        *,
        search: str = "",
        status: str = "",
    ) -> list[dict[str, Any]]:
        rows = [row for row in self.audit_logs if in_scope(row["path"], scope_path)]
        if status and status != "all":
            rows = [row for row in rows if row["status"] == status]
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["actor"].lower()
                or term in row["action"].lower()
                or term in row["target"].lower()
                or term in row["scope_label"].lower()
            ]
        return sorted(rows, key=lambda row: row["time"], reverse=True)

    def list_rbac_roles(self) -> list[dict[str, Any]]:
        return sorted(self.rbac_roles, key=lambda row: row["level"])

    def get_rbac_role(self, role_id: str) -> dict[str, Any] | None:
        return next((row for row in self.rbac_roles if row["role_id"] == role_id), None)

    def list_rbac_permissions(self, *, family: str = "", search: str = "") -> list[dict[str, Any]]:
        rows = self.rbac_permissions
        if family and family != "all":
            rows = [row for row in rows if row["family"] == family]
        if search:
            term = search.lower().strip()
            rows = [row for row in rows if term in row["family"].lower() or term in row["key"].lower()]
        return sorted(rows, key=lambda row: (row["family"], row["key"]))

    def get_rbac_permission(self, permission_id: str) -> dict[str, Any] | None:
        return next((row for row in self.rbac_permissions if row["permission_id"] == permission_id), None)

    def list_role_permissions(self, role_id: str) -> list[dict[str, Any]]:
        role = self.get_rbac_role(role_id)
        if role is None:
            return []
        permission_ids = set(role.get("permission_ids", []))
        rows = [row for row in self.rbac_permissions if row["permission_id"] in permission_ids]
        return sorted(rows, key=lambda row: (row["family"], row["key"]))

    def update_rbac_role(
        self,
        role_id: str,
        payload: dict[str, str],
        *,
        actor_name: str,
    ) -> dict[str, Any] | None:
        role = self.get_rbac_role(role_id)
        if role is None:
            return None
        role["description"] = payload.get("description", role.get("description", "")).strip()
        role["scope"] = payload.get("scope", role.get("scope", ""))
        role["status"] = payload.get("status", role.get("status", "active"))
        permission_ids = []
        for permission in self.rbac_permissions:
            if payload.get(f"perm_{permission['permission_id']}") == "on":
                permission_ids.append(permission["permission_id"])
        role["permission_ids"] = permission_ids
        role["permission_count"] = len(permission_ids)
        self.audit_logs.insert(
            0,
            {
                "log_id": f"aud-{len(self.audit_logs) + 1:03d}",
                "time": f"{TODAY.isoformat()} 10:55",
                "actor": actor_name,
                "action": "Updated RBAC role",
                "target": role["name"],
                "status": "success",
                "scope_label": "Global",
                "path": "global",
            },
        )
        self.system_notifications.insert(
            0,
            {
                "notification_id": f"sysn-{len(self.system_notifications) + 1:03d}",
                "title": f"RBAC role updated: {role['name']}",
                "body": "A governance role was updated in the RBAC studio and should be reviewed if this was a production change.",
                "kind": "rbac",
                "priority": "medium",
                "status": "unread",
                "time": f"{TODAY.isoformat()} 10:55",
                "path": "global",
            },
        )
        return role

    def run_system_utility(self, action: str, *, actor_name: str) -> dict[str, str]:
        message_map = {
            "seed_programs": "Program reference data seeded successfully.",
            "refresh_notifications": "Notification queue refreshed.",
            "rebuild_reports": "Report refresh job queued successfully.",
        }
        message = message_map.get(action, "System utility completed.")
        self.audit_logs.insert(
            0,
            {
                "log_id": f"aud-{len(self.audit_logs) + 1:03d}",
                "time": f"{TODAY.isoformat()} 10:50",
                "actor": actor_name,
                "action": "Ran utility",
                "target": action,
                "status": "success",
                "scope_label": "Global",
                "path": "global",
            },
        )
        return {"action": action, "message": message}

    def _build_hierarchy_index(self, scope_path: str) -> dict[str, dict[str, Any]]:
        nodes: dict[str, dict[str, Any]] = {}

        def is_visible(path: str) -> bool:
            return path == scope_path or in_scope(path, scope_path)

        def add_node(path: str, label: str, kind: str, parent_path: str | None, **extra: Any) -> None:
            if not is_visible(path):
                return
            if path not in nodes:
                nodes[path] = {
                    "path": path,
                    "label": label,
                    "kind": kind,
                    "parent_path": parent_path,
                    "children_count": 0,
                    "entity_id": extra.get("entity_id", ""),
                    "location_key": extra.get("location_key", ""),
                    "depth": len(path.split(".")) - len(scope_path.split(".")),
                }

        add_node("global", "Global", "global", None, entity_id="global")
        for row in LOCATIONS:
            continent_path = "global.west_africa"
            nation_path = "global.west_africa.nigeria"
            state_path = SCOPE_PATHS["state"][row["state"]]
            region_path = SCOPE_PATHS["region"][row["region"]]
            group_path = SCOPE_PATHS["group"][row["group"]]
            location_path = row["path"]
            location_key = location_path.split(".")[-1]
            add_node(continent_path, row["continent"], "continent", "global", entity_id=row["continent"])
            add_node(nation_path, row["nation"], "nation", continent_path, entity_id=row["nation"])
            add_node(state_path, row["state"], "state", nation_path, entity_id=row["state"])
            add_node(region_path, row["region"], "region", state_path, entity_id=row["region"])
            add_node(group_path, row["group"], "group", region_path, entity_id=row["group"])
            add_node(location_path, row["location"], "location", group_path, entity_id=row["location"], location_key=location_key)

        for row in self.fellowships:
            fellowship_path = f"{row['path']}.{row['fellowship_id'].replace('-', '_')}"
            add_node(
                fellowship_path,
                row["name"],
                "fellowship",
                row["path"],
                entity_id=row["fellowship_id"],
                location_key=row["path"].split(".")[-1],
            )

        for node in nodes.values():
            parent_path = node["parent_path"]
            if parent_path and parent_path in nodes:
                nodes[parent_path]["children_count"] += 1

            path = node["path"]
            if node["kind"] == "fellowship":
                fellowship = self.get_fellowship(node["entity_id"])
                if fellowship:
                    node["member_count"] = len(self.list_fellowship_members(fellowship["fellowship_id"]))
                    node["location_count"] = 1
                    node["fellowship_count"] = 1
                    node["worker_count"] = 0
            else:
                node["location_count"] = len([profile for profile in self.location_profiles if in_scope(profile["path"], path)])
                node["fellowship_count"] = len([fellowship for fellowship in self.fellowships if in_scope(fellowship["path"], path)])
                node["member_count"] = len(self.list_church_members(path))
                node["worker_count"] = len(self.list_workers(path))
        return nodes

    def list_hierarchy_tree(self, scope_path: str) -> list[dict[str, Any]]:
        nodes = self._build_hierarchy_index(scope_path)
        return sorted(nodes.values(), key=lambda row: (row["depth"], row["label"]))

    def get_hierarchy_node(self, scope_path: str, node_path: str) -> dict[str, Any] | None:
        return self._build_hierarchy_index(scope_path).get(node_path)

    def list_hierarchy_children(self, scope_path: str, node_path: str) -> list[dict[str, Any]]:
        nodes = self._build_hierarchy_index(scope_path)
        rows = [row for row in nodes.values() if row["parent_path"] == node_path]
        return sorted(rows, key=lambda row: (row["kind"], row["label"]))

    def list_program_domains(self) -> list[dict[str, Any]]:
        rows = []
        for domain in self.program_domains:
            event_count = sum(1 for event in self.program_events if event["domain_id"] == domain["domain_id"])
            rows.append({**domain, "event_count": event_count})
        return sorted(rows, key=lambda row: row["name"])

    def get_program_domain(self, domain_id: str) -> dict[str, Any] | None:
        return next((row for row in self.program_domains if row["domain_id"] == domain_id), None)

    def add_program_domain(self, payload: dict[str, str]) -> dict[str, Any]:
        next_index = len(self.program_domains) + 1
        row = {
            "domain_id": f"dom-{next_index:03d}",
            "name": payload["name"].strip(),
            "description": payload.get("description", "").strip(),
        }
        self.program_domains.insert(0, row)
        return row

    def list_program_types(self, *, domain_id: str = "") -> list[dict[str, Any]]:
        rows = self.program_types
        if domain_id:
            rows = [row for row in rows if row["domain_id"] == domain_id]
        result = []
        for row in rows:
            event_count = sum(1 for event in self.program_events if event["type_id"] == row["type_id"])
            result.append({**row, "event_count": event_count})
        return sorted(result, key=lambda row: (row["domain_name"], row["name"]))

    def get_program_type(self, type_id: str) -> dict[str, Any] | None:
        return next((row for row in self.program_types if row["type_id"] == type_id), None)

    def add_program_type(self, payload: dict[str, str]) -> dict[str, Any]:
        domain = self.get_program_domain(payload["domain_id"])
        next_index = len(self.program_types) + 1
        row = {
            "type_id": f"typ-{next_index:03d}",
            "domain_id": payload["domain_id"],
            "domain_name": domain["name"] if domain else "",
            "name": payload["name"].strip(),
            "description": payload.get("description", "").strip(),
        }
        self.program_types.insert(0, row)
        return row

    def list_program_events(
        self,
        scope_path: str,
        *,
        domain_id: str = "",
        type_id: str = "",
        location: str = "",
        status: str = "",
        search: str = "",
    ) -> list[dict[str, Any]]:
        rows = [event for event in self.program_events if in_scope(event["path"], scope_path)]
        if domain_id:
            rows = [row for row in rows if row["domain_id"] == domain_id]
        if type_id:
            rows = [row for row in rows if row["type_id"] == type_id]
        if location:
            rows = [row for row in rows if row["location"] == location]
        if status:
            rows = [row for row in rows if row["status"] == status]
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["title"].lower()
                or term in row["program_type"].lower()
                or term in row["domain_name"].lower()
                or term in row["location"].lower()
            ]
        return sorted(rows, key=lambda row: (row["date"], row["title"]), reverse=True)

    def get_program_event(self, event_id: str) -> dict[str, Any] | None:
        return next((row for row in self.program_events if row["event_id"] == event_id), None)

    def add_program_event(self, payload: dict[str, str]) -> dict[str, Any]:
        program_type = self.get_program_type(payload["type_id"])
        domain = self.get_program_domain(payload["domain_id"])
        location = LOCATION_LOOKUP[payload["location"]]
        next_index = len(self.program_events) + 1
        row = {
            "event_id": f"evt-{next_index:03d}",
            "title": payload["title"].strip(),
            "domain_id": payload["domain_id"],
            "domain_name": domain["name"] if domain else "",
            "type_id": payload["type_id"],
            "program_type": program_type["name"] if program_type else "",
            "date": payload["date"],
            "status": payload.get("status", "scheduled"),
            "level": "location",
            "location": location["location"],
            "created_by": payload["created_by"].strip(),
            "path": location["path"],
        }
        self.program_events.insert(0, row)
        self.activity.insert(
            0,
            {
                "message": f"Program event created: {row['title']}",
                "meta": f"{row['location']} | Just now",
                "tone": "info",
                "path": row["path"],
            },
        )
        return row

    def list_workers(self, scope_path: str, *, search: str = "", status: str = "", approval: str = "") -> list[dict[str, Any]]:
        rows = [row for row in self.workers if in_scope(row["path"], scope_path)]
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["name"].lower()
                or term in row["unit"].lower()
                or term in row["location"].lower()
                or term in row["user_id"].lower()
            ]
        if status:
            rows = [row for row in rows if row["status"] == status]
        if approval:
            rows = [row for row in rows if row["approval_status"] == approval]
        return sorted(rows, key=_sort_key)

    def get_worker(self, worker_id: str) -> dict[str, Any] | None:
        return next((row for row in self.workers if row["worker_id"] == worker_id), None)

    def add_worker(self, payload: dict[str, str]) -> dict[str, Any]:
        location = LOCATION_LOOKUP[payload["location"]]
        next_index = len(self.workers) + 1
        worker = {
            "worker_id": f"wrk-{next_index:03d}",
            "user_id": f"W-{next_index:03d}",
            "name": payload["name"].strip(),
            "gender": payload["gender"],
            "phone": payload["phone"].strip(),
            "unit": payload["unit"],
            "status": "Pending Verification",
            "approval_status": "pending_verification",
            "location": location["location"],
            "group": location["group"],
            "region": location["region"],
            "state": location["state"],
            "added_date": TODAY.isoformat(),
            "path": location["path"],
        }
        self.workers.insert(0, worker)
        self.inbox.insert(
            0,
            {
                "item_id": f"inbox-{len(self.inbox) + 1:03d}",
                "kind": "worker_registration",
                "title": "Approve worker registration",
                "subject": worker["name"],
                "worker_id": worker["worker_id"],
                "location": worker["location"],
                "path": worker["path"],
                "submitted_at": "Just now",
                "priority": "High",
                "current_stage": "Waiting for location review",
                "summary": f"{worker['unit']} unit registration is waiting for approval before account creation.",
                "resolved": False,
            },
        )
        self.activity.insert(
            0,
            {
                "message": f"Worker registration created for {worker['name']}",
                "meta": f"{worker['location']} | Just now",
                "tone": "info",
                "path": worker["path"],
            },
        )
        return worker

    def suspend_worker(self, worker_id: str, *, actor_name: str, note: str = "") -> dict[str, Any] | None:
        worker = self.get_worker(worker_id)
        if worker is None:
            return None
        worker["status"] = "Suspended"
        if note.strip():
            worker["status_note"] = note.strip()
        self.activity.insert(
            0,
            {
                "message": f"Worker suspended: {worker['name']}",
                "meta": f"{actor_name} - Just now",
                "tone": "warning",
                "path": worker["path"],
            },
        )
        return worker

    def list_users(self, scope_path: str, *, search: str = "", approval: str = "", status: str = "") -> list[dict[str, Any]]:
        rows = [row for row in self.users if in_scope(row["path"], scope_path)]
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["name"].lower()
                or term in row["location"].lower()
                or any(term in role.lower() for role in row["roles"])
            ]
        if approval:
            rows = [row for row in rows if row["approval_status"] == approval]
        if status:
            rows = [row for row in rows if row["status"] == status]
        return sorted(rows, key=_sort_key)

    def get_user(self, account_id: str) -> dict[str, Any] | None:
        return next((row for row in self.users if row["account_id"] == account_id), None)

    def get_user_by_worker(self, worker_id: str) -> dict[str, Any] | None:
        return next((row for row in self.users if row.get("worker_id") == worker_id), None)

    def add_user(self, payload: dict[str, str]) -> dict[str, Any]:
        location = LOCATION_LOOKUP[payload["location"]]
        next_index = len(self.users) + 1
        roles = [payload["role"]]
        row = {
            "account_id": f"usr-{next_index:03d}",
            "name": payload["name"].strip(),
            "phone": payload["phone"].strip(),
            "location": location["location"],
            "roles": roles,
            "approval_status": "pending",
            "status": "inactive",
            "worker_id": payload.get("worker_id", ""),
            "path": location["path"],
        }
        self.users.insert(0, row)
        self.inbox.insert(
            0,
            {
                "item_id": f"inbox-{len(self.inbox) + 1:03d}",
                "kind": "user_approval",
                "title": "Approve app access",
                "subject": row["name"],
                "account_id": row["account_id"],
                "worker_id": row.get("worker_id", ""),
                "location": row["location"],
                "path": row["path"],
                "submitted_at": "Just now",
                "priority": "Medium",
                "current_stage": "Waiting for location review",
                "summary": f"{roles[0]} access request is waiting for approval.",
                "resolved": False,
            },
        )
        return row

    def update_user_roles(self, account_id: str, roles: list[str], *, actor_name: str) -> dict[str, Any] | None:
        user = self.get_user(account_id)
        if user is None:
            return None
        cleaned_roles = []
        for role in roles:
            value = role.strip()
            if value and value not in cleaned_roles:
                cleaned_roles.append(value)
        if not cleaned_roles:
            return user
        user["roles"] = cleaned_roles
        if user["approval_status"] == "pending":
            user["approval_status"] = "approved"
        if user["status"] == "inactive":
            user["status"] = "active"
        self.activity.insert(
            0,
            {
                "message": f"User roles updated for {user['name']}",
                "meta": f"{actor_name} - Just now",
                "tone": "info",
                "path": user["path"],
            },
        )
        return user

    def deactivate_user(self, account_id: str, *, actor_name: str, note: str = "") -> dict[str, Any] | None:
        user = self.get_user(account_id)
        if user is None:
            return None
        user["status"] = "inactive"
        if note.strip():
            user["deactivation_note"] = note.strip()
        self.activity.insert(
            0,
            {
                "message": f"User account deactivated for {user['name']}",
                "meta": f"{actor_name} - Just now",
                "tone": "warning",
                "path": user["path"],
            },
        )
        return user

    def list_official_appointments(
        self,
        scope_path: str,
        *,
        search: str = "",
        status: str = "",
        appointed_role: str = "",
    ) -> list[dict[str, Any]]:
        rows = [row for row in self.official_appointments if in_scope(row["path"], scope_path)]
        if status:
            rows = [row for row in rows if row["status"] == status]
        if appointed_role:
            rows = [row for row in rows if row["appointed_role"] == appointed_role]
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["worker_name"].lower()
                or term in row["appointed_role"].lower()
                or term in row["assigned_scope"].lower()
                or term in row["appointed_by"].lower()
            ]
        return sorted(rows, key=lambda row: (row["status"], row["appointment_date"], row["worker_name"]), reverse=True)

    def get_official_appointment(self, appointment_id: str) -> dict[str, Any] | None:
        return next((row for row in self.official_appointments if row["appointment_id"] == appointment_id), None)

    def official_appointment_summary(self, scope_path: str) -> dict[str, int]:
        rows = self.list_official_appointments(scope_path)
        return {
            "total": len(rows),
            "active": sum(1 for row in rows if row["status"] == "active"),
            "revoked": sum(1 for row in rows if row["status"] == "revoked"),
            "scopes": len({row["assigned_scope"] for row in rows}),
        }

    def add_official_appointment(self, payload: dict[str, str], *, actor_name: str) -> dict[str, Any]:
        worker = self.get_worker(payload["worker_id"])
        if worker is None:
            raise KeyError("worker_id")
        next_index = len(self.official_appointments) + 1
        row = {
            "appointment_id": f"off-{next_index:03d}",
            "worker_id": worker["worker_id"],
            "worker_name": worker["name"],
            "appointed_role": payload["appointed_role"].strip(),
            "assigned_scope": payload["assigned_scope"].strip(),
            "appointed_by": actor_name,
            "appointment_date": payload.get("appointment_date", TODAY.isoformat()),
            "status": payload.get("status", "active"),
            "location": worker["location"],
            "path": payload.get("assigned_scope_path", worker["path"]),
        }
        self.official_appointments.insert(0, row)
        self.activity.insert(
            0,
            {
                "message": f"Official appointment added for {row['worker_name']}",
                "meta": f"{row['location']} | Just now",
                "tone": "success",
                "path": row["path"],
            },
        )
        return row

    def update_official_appointment(self, appointment_id: str, payload: dict[str, str], *, actor_name: str) -> dict[str, Any] | None:
        row = self.get_official_appointment(appointment_id)
        if row is None:
            return None
        for field in ["appointed_role", "assigned_scope", "appointment_date", "status"]:
            value = payload.get(field)
            if value is not None and value.strip():
                row[field] = value.strip()
        if payload.get("assigned_scope_path", "").strip():
            row["path"] = payload["assigned_scope_path"].strip()
        self.activity.insert(
            0,
            {
                "message": f"Official appointment updated for {row['worker_name']}",
                "meta": f"{actor_name} - Just now",
                "tone": "info",
                "path": row["path"],
            },
        )
        return row

    def revoke_official_appointment(self, appointment_id: str, *, actor_name: str, note: str = "") -> dict[str, Any] | None:
        row = self.get_official_appointment(appointment_id)
        if row is None:
            return None
        row["status"] = "revoked"
        if note.strip():
            row["revoke_note"] = note.strip()
        self.activity.insert(
            0,
            {
                "message": f"Official appointment revoked for {row['worker_name']}",
                "meta": f"{actor_name} - Just now",
                "tone": "warning",
                "path": row["path"],
            },
        )
        return row

    def list_church_members(
        self,
        scope_path: str,
        *,
        search: str = "",
        location: str = "",
        status: str = "",
        fellowship_id: str = "",
    ) -> list[dict[str, Any]]:
        rows = [row for row in self.church_members if in_scope(row["path"], scope_path)]
        if location:
            rows = [row for row in rows if row["location"] == location]
        if status:
            rows = [row for row in rows if row["status"] == status]
        if fellowship_id:
            rows = [row for row in rows if row["fellowship_id"] == fellowship_id]
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["name"].lower()
                or term in row["phone"].lower()
                or term in row["location"].lower()
                or term in row["fellowship_name"].lower()
            ]
        return sorted(rows, key=_sort_key)

    def get_church_member(self, member_id: str) -> dict[str, Any] | None:
        return next((row for row in self.church_members if row["member_id"] == member_id), None)

    def add_church_member(self, payload: dict[str, str]) -> dict[str, Any]:
        fellowship_id = payload.get("fellowship_id", "").strip()
        fellowship = self.get_fellowship(fellowship_id) if fellowship_id else None
        location_name = payload.get("location", "").strip() or (fellowship["location"] if fellowship else "")
        if not location_name:
            raise KeyError("location")
        location = LOCATION_LOOKUP[location_name]
        next_index = len(self.church_members) + 1
        row = {
            "member_id": f"mem-{next_index:03d}",
            "name": payload["name"].strip(),
            "phone": payload["phone"].strip(),
            "gender": payload["gender"],
            "marital_status": payload["marital_status"],
            "location": location["location"],
            "fellowship_id": fellowship["fellowship_id"] if fellowship else "",
            "fellowship_name": fellowship["name"] if fellowship else "",
            "status": payload.get("status", "active"),
            "date_joined": payload.get("date_joined", TODAY.isoformat()),
            "path": location["path"],
        }
        self.church_members.insert(0, row)
        destination = row["fellowship_name"] or row["location"]
        self.activity.insert(
            0,
            {
                "message": f"Church member added: {row['name']}",
                "meta": f"{destination} - Just now",
                "tone": "success",
                "path": row["path"],
            },
        )
        return row

    def church_member_summary(self, scope_path: str) -> dict[str, Any]:
        rows = self.list_church_members(scope_path)
        return {
            "total": len(rows),
            "active": sum(1 for row in rows if row["status"] == "active"),
            "transferred": sum(1 for row in rows if row["status"] == "transferred"),
            "inactive": sum(1 for row in rows if row["status"] == "inactive"),
            "fellowships": len({row["fellowship_id"] for row in rows if row["fellowship_id"]}),
        }

    def list_fellowships(
        self,
        scope_path: str,
        *,
        search: str = "",
        location: str = "",
        status: str = "",
    ) -> list[dict[str, Any]]:
        rows = [row for row in self.fellowships if in_scope(row["path"], scope_path)]
        if location:
            rows = [row for row in rows if row["location"] == location]
        if status:
            rows = [row for row in rows if row["status"] == status]
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["name"].lower()
                or term in row["location"].lower()
                or term in row["leader_name"].lower()
                or term in row["assistant_name"].lower()
            ]
        result = []
        for row in rows:
            members = self.list_fellowship_members(row["fellowship_id"])
            attendance = self.list_fellowship_attendance(row["fellowship_id"])
            offerings = self.list_fellowship_offerings(row["fellowship_id"])
            prayers = self.list_fellowship_prayers(row["fellowship_id"])
            result.append(
                {
                    **row,
                    "member_count": len(members),
                    "active_members": sum(1 for member in members if member["status"] == "active"),
                    "last_attendance": attendance[0]["total"] if attendance else 0,
                    "last_offering": offerings[0]["amount"] if offerings else 0,
                    "open_prayers": sum(1 for prayer in prayers if prayer["status"] in {"new", "ongoing"}),
                }
            )
        return sorted(result, key=lambda row: (row["location"], row["name"]))

    def get_fellowship(self, fellowship_id: str) -> dict[str, Any] | None:
        return next((row for row in self.fellowships if row["fellowship_id"] == fellowship_id), None)

    def fellowship_summary(self, scope_path: str) -> dict[str, Any]:
        rows = self.list_fellowships(scope_path)
        return {
            "total": len(rows),
            "members": sum(row["member_count"] for row in rows),
            "active": sum(1 for row in rows if row["status"] == "active"),
            "average_attendance": int(sum(row["last_attendance"] for row in rows) / len(rows)) if rows else 0,
            "open_prayers": sum(row["open_prayers"] for row in rows),
        }

    def fellowship_detail_summary(self, fellowship_id: str) -> dict[str, Any]:
        members = self.list_fellowship_members(fellowship_id)
        attendance = self.list_fellowship_attendance(fellowship_id)
        offerings = self.list_fellowship_offerings(fellowship_id)
        testimonies = self.list_fellowship_testimonies(fellowship_id)
        prayers = self.list_fellowship_prayers(fellowship_id)
        summaries = self.list_fellowship_summaries(fellowship_id)
        return {
            "member_count": len(members),
            "active_members": sum(1 for row in members if row["status"] == "active"),
            "last_attendance": attendance[0]["total"] if attendance else 0,
            "last_offering": offerings[0]["amount"] if offerings else 0,
            "testimonies": len(testimonies),
            "open_prayers": sum(1 for row in prayers if row["status"] in {"new", "ongoing"}),
            "latest_summary": summaries[0] if summaries else None,
        }

    def list_fellowship_members(self, fellowship_id: str) -> list[dict[str, Any]]:
        return sorted(
            [row for row in self.church_members if row["fellowship_id"] == fellowship_id],
            key=_sort_key,
        )

    def list_fellowship_attendance(self, fellowship_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self.fellowship_attendance if row["fellowship_id"] == fellowship_id]
        return sorted(rows, key=lambda row: row["date"], reverse=True)

    def list_fellowship_offerings(self, fellowship_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self.fellowship_offerings if row["fellowship_id"] == fellowship_id]
        return sorted(rows, key=lambda row: row["date"], reverse=True)

    def list_fellowship_testimonies(self, fellowship_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self.fellowship_testimonies if row["fellowship_id"] == fellowship_id]
        return sorted(rows, key=lambda row: row["date"], reverse=True)

    def list_fellowship_prayers(self, fellowship_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self.fellowship_prayers if row["fellowship_id"] == fellowship_id]
        return sorted(rows, key=lambda row: row["date"], reverse=True)

    def list_fellowship_summaries(self, fellowship_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self.fellowship_summaries if row["fellowship_id"] == fellowship_id]
        return sorted(rows, key=lambda row: row["week_of"], reverse=True)

    def add_fellowship_offering(self, payload: dict[str, str]) -> dict[str, Any]:
        fellowship = self.get_fellowship(payload["fellowship_id"])
        if fellowship is None:
            raise KeyError("fellowship_id")
        next_index = len(self.fellowship_offerings) + 1
        row = {
            "offering_id": f"fso-{next_index:03d}",
            "fellowship_id": fellowship["fellowship_id"],
            "date": payload["date"],
            "amount": int(payload["amount"]),
            "method": payload["method"],
            "submitted_by": payload["submitted_by"].strip(),
            "location": fellowship["location"],
            "notes": payload.get("notes", "").strip(),
            "path": fellowship["path"],
        }
        self.fellowship_offerings.insert(0, row)
        self.activity.insert(
            0,
            {
                "message": f"Fellowship offering recorded for {fellowship['name']}",
                "meta": f"{fellowship['location']} - Just now",
                "tone": "success",
                "path": fellowship["path"],
            },
        )
        return row

    def add_fellowship_testimony(self, payload: dict[str, str]) -> dict[str, Any]:
        fellowship = self.get_fellowship(payload["fellowship_id"])
        if fellowship is None:
            raise KeyError("fellowship_id")
        next_index = len(self.fellowship_testimonies) + 1
        row = {
            "testimony_id": f"fst-{next_index:03d}",
            "fellowship_id": fellowship["fellowship_id"],
            "member_name": payload["member_name"].strip(),
            "summary": payload["summary"].strip(),
            "date": payload["date"],
            "status": payload.get("status", "shared"),
            "path": fellowship["path"],
        }
        self.fellowship_testimonies.insert(0, row)
        self.activity.insert(
            0,
            {
                "message": f"New fellowship testimony added in {fellowship['name']}",
                "meta": f"{fellowship['location']} - Just now",
                "tone": "info",
                "path": fellowship["path"],
            },
        )
        return row

    def add_fellowship_prayer(self, payload: dict[str, str]) -> dict[str, Any]:
        fellowship = self.get_fellowship(payload["fellowship_id"])
        if fellowship is None:
            raise KeyError("fellowship_id")
        next_index = len(self.fellowship_prayers) + 1
        row = {
            "prayer_id": f"fsp-{next_index:03d}",
            "fellowship_id": fellowship["fellowship_id"],
            "requester_name": payload["requester_name"].strip(),
            "summary": payload["summary"].strip(),
            "date": payload["date"],
            "status": payload.get("status", "new"),
            "path": fellowship["path"],
        }
        self.fellowship_prayers.insert(0, row)
        self.activity.insert(
            0,
            {
                "message": f"Prayer request added in {fellowship['name']}",
                "meta": f"{fellowship['location']} - Just now",
                "tone": "warning",
                "path": fellowship["path"],
            },
        )
        return row

    def list_counts(self, scope_path: str, *, location: str = "", event_title: str = "") -> list[dict[str, Any]]:
        rows = [row for row in self.counts if in_scope(row["path"], scope_path)]
        if location:
            rows = [row for row in rows if row["location"] == location]
        if event_title:
            rows = [row for row in rows if row["event_title"] == event_title]
        return sorted(rows, key=lambda row: (row["date"], row["location"]), reverse=True)

    def get_count(self, count_id: str) -> dict[str, Any] | None:
        return next((row for row in self.counts if row["count_id"] == count_id), None)

    def add_count(self, payload: dict[str, str]) -> dict[str, Any]:
        location = LOCATION_LOOKUP[payload["location"]]
        total = sum(
            int(payload[field])
            for field in ["adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls"]
        )
        next_index = len(self.counts) + 1
        row = {
            "count_id": f"cnt-{next_index:03d}",
            "event_title": payload["event_title"],
            "event_id": payload.get("event_id") or "",
            "date": payload["date"],
            "location": location["location"],
            "group": location["group"],
            "region": location["region"],
            "state": location["state"],
            "adult_male": int(payload["adult_male"]),
            "adult_female": int(payload["adult_female"]),
            "youth_male": int(payload["youth_male"]),
            "youth_female": int(payload["youth_female"]),
            "boys": int(payload["boys"]),
            "girls": int(payload["girls"]),
            "total": total,
            "submitted_by": payload["submitted_by"].strip(),
            "path": location["path"],
        }
        self.counts.insert(0, row)
        self.activity.insert(
            0,
            {
                "message": f"{row['event_title']} count submitted for {row['location']}",
                "meta": f"{row['location']} | Just now",
                "tone": "success",
                "path": row["path"],
            },
        )
        return row

    def list_finance(
        self,
        scope_path: str,
        *,
        fund_type: str = "",
        location: str = "",
        method: str = "",
    ) -> list[dict[str, Any]]:
        rows = [row for row in self.finance if in_scope(row["path"], scope_path)]
        if fund_type and fund_type != "all":
            rows = [row for row in rows if row["fund_type"] == fund_type]
        if location:
            rows = [row for row in rows if row["location"] == location]
        if method:
            rows = [row for row in rows if row["method"] == method]
        return sorted(rows, key=lambda row: (row["date"], row["location"]), reverse=True)

    def get_finance_entry(self, entry_id: str) -> dict[str, Any] | None:
        return next((row for row in self.finance if row["entry_id"] == entry_id), None)

    def add_finance(self, payload: dict[str, str]) -> dict[str, Any]:
        location = LOCATION_LOOKUP[payload["location"]]
        next_index = len(self.finance) + 1
        row = {
            "entry_id": f"fin-{next_index:03d}",
            "fund_type": payload["fund_type"],
            "amount": int(payload["amount"]),
            "date": payload["date"],
            "method": payload["method"],
            "event_title": payload["event_title"],
            "location": location["location"],
            "submitted_by": payload["submitted_by"].strip(),
            "notes": payload.get("notes", "").strip(),
            "path": location["path"],
        }
        self.finance.insert(0, row)
        self.activity.insert(
            0,
            {
                "message": f"{row['fund_type'].title()} recorded for {row['location']}",
                "meta": f"{row['location']} | Just now",
                "tone": "success",
                "path": row["path"],
            },
        )
        return row

    def finance_summary(self, scope_path: str) -> dict[str, Any]:
        rows = self.list_finance(scope_path)
        if not rows:
            return {
                "month_total": 0,
                "year_total": 0,
                "average_entry": 0,
                "entries": 0,
                "offering_total": 0,
                "tithe_total": 0,
            }
        offering_total = sum(row["amount"] for row in rows if row["fund_type"] == "offering")
        tithe_total = sum(row["amount"] for row in rows if row["fund_type"] == "tithe")
        month_total = sum(row["amount"] for row in rows if row["date"].startswith("2026-03"))
        year_total = sum(row["amount"] for row in rows if row["date"].startswith("2026"))
        return {
            "month_total": month_total,
            "year_total": year_total,
            "average_entry": int((offering_total + tithe_total) / len(rows)),
            "offering_total": offering_total,
            "tithe_total": tithe_total,
            "entries": len(rows),
        }

    def list_records(
        self,
        scope_path: str,
        *,
        record_type: str = "",
        status: str = "",
        search: str = "",
        location: str = "",
        gender: str = "",
    ) -> list[dict[str, Any]]:
        rows = [row for row in self.records if in_scope(row["path"], scope_path)]
        if record_type and record_type != "all":
            rows = [row for row in rows if row["record_type"] == record_type]
        if status:
            rows = [row for row in rows if row["status"] == status]
        if location:
            rows = [row for row in rows if row["location"] == location]
        if gender:
            rows = [row for row in rows if row.get("gender", "") == gender]
        if search:
            term = search.lower().strip()
            rows = [
                row
                for row in rows
                if term in row["name"].lower()
                or term in row["phone"].lower()
                or term in row["location"].lower()
                or term in row["service"].lower()
            ]
        return sorted(rows, key=lambda row: (row["date"], row["location"]), reverse=True)

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        return next((row for row in self.records if row["record_id"] == record_id), None)

    def add_record(self, payload: dict[str, str]) -> dict[str, Any]:
        location = LOCATION_LOOKUP[payload["location"]]
        next_index = len(self.records) + 1
        row = {
            "record_id": f"rec-{next_index:03d}",
            "record_type": payload["record_type"],
            "name": payload["name"].strip(),
            "phone": payload["phone"].strip(),
            "gender": payload["gender"],
            "location": location["location"],
            "status": payload["status"],
            "date": payload["date"],
            "service": payload["service"],
            "assigned_to": payload["assigned_to"].strip(),
            "notes": payload.get("notes", "").strip(),
            "path": location["path"],
        }
        self.records.insert(0, row)
        self.activity.insert(
            0,
            {
                "message": f"{row['record_type'].title()} record added for {row['name']}",
                "meta": f"{row['location']} | Just now",
                "tone": "info",
                "path": row["path"],
            },
        )
        return row

    def record_summary(self, scope_path: str) -> dict[str, Any]:
        rows = self.list_records(scope_path)
        return {
            "total": len(rows),
            "newcomers": sum(1 for row in rows if row["record_type"] == "newcomer"),
            "converts": sum(1 for row in rows if row["record_type"] == "convert"),
            "pending_follow_up": sum(1 for row in rows if row["status"] == "follow_up_pending"),
        }

    def list_attendance(
        self,
        scope_path: str,
        *,
        status: str = "",
        location: str = "",
        unit: str = "",
        event_title: str = "",
    ) -> list[dict[str, Any]]:
        rows = [row for row in self.attendance if in_scope(row["path"], scope_path)]
        if status:
            rows = [row for row in rows if row["status"] == status]
        if location:
            rows = [row for row in rows if row["location"] == location]
        if unit:
            rows = [row for row in rows if row["unit"] == unit]
        if event_title:
            rows = [row for row in rows if row["event_title"] == event_title]
        return sorted(rows, key=lambda row: (row["date"], row["location"]), reverse=True)

    def get_attendance_entry(self, attendance_id: str) -> dict[str, Any] | None:
        return next((row for row in self.attendance if row["attendance_id"] == attendance_id), None)

    def add_attendance(self, payload: dict[str, str]) -> dict[str, Any]:
        location = LOCATION_LOOKUP[payload["location"]]
        worker = self.get_worker(payload["worker_id"])
        next_index = len(self.attendance) + 1
        row = {
            "attendance_id": f"att-{next_index:03d}",
            "worker_id": payload["worker_id"],
            "worker_name": worker["name"] if worker else payload.get("worker_name", ""),
            "unit": worker["unit"] if worker else payload.get("unit", ""),
            "status": payload["status"],
            "event_title": payload["event_title"],
            "date": payload["date"],
            "location": location["location"],
            "recorded_by": payload["recorded_by"].strip(),
            "reason": payload.get("reason", "").strip(),
            "path": location["path"],
        }
        self.attendance.insert(0, row)
        self.activity.insert(
            0,
            {
                "message": f"Attendance marked for {row['worker_name']}",
                "meta": f"{row['location']} | Just now",
                "tone": "success" if row["status"] == "present" else "warning",
                "path": row["path"],
            },
        )
        return row

    def attendance_summary(self, scope_path: str) -> dict[str, Any]:
        rows = self.list_attendance(scope_path)
        expected = len(self.list_workers(scope_path))
        present = sum(1 for row in rows if row["status"] == "present")
        absent = sum(1 for row in rows if row["status"] == "absent")
        late = sum(1 for row in rows if row["status"] == "late")
        return {
            "expected": expected,
            "present": present,
            "absent": absent,
            "late": late,
            "excused": sum(1 for row in rows if row["status"] == "excused"),
            "rate": int((present / expected) * 100) if expected else 0,
            "records": len(rows),
        }

    def list_requests(
        self,
        scope_path: str,
        *,
        request_type: str = "",
        status: str = "",
        requester: str = "",
        mine_only: bool = False,
        review_only: bool = False,
    ) -> list[dict[str, Any]]:
        rows = [row for row in self.requests if in_scope(row["path"], scope_path)]
        if request_type and request_type != "all":
            rows = [row for row in rows if row["request_type"] == request_type]
        if status and status != "all":
            rows = [row for row in rows if row["status"] == status]
        if mine_only and requester:
            rows = [row for row in rows if row["requested_by"] == requester]
        if review_only and requester:
            rows = [row for row in rows if row["requested_by"] != requester and row["status"] in {"pending", "escalated"}]
        return sorted(rows, key=lambda row: row["submitted_at"], reverse=True)

    def get_request(self, request_id: str) -> dict[str, Any] | None:
        return next((row for row in self.requests if row["request_id"] == request_id), None)

    def list_worker_requests(self, worker_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self.requests if row["worker_id"] == worker_id]
        return sorted(rows, key=lambda row: row["submitted_at"], reverse=True)

    def add_request(self, payload: dict[str, str], requester_name: str) -> dict[str, Any]:
        worker = self.get_worker(payload["worker_id"])
        if worker is None:
            raise KeyError("worker_id")
        request_type = payload["request_type"]
        next_index = len(self.requests) + 1
        summary_map = {
            "transfer_request": f"Transfer request from {worker['location']} to {payload.get('destination_location', '').strip()}.",
            "status_change": f"Status change request raised for {worker['name']}.",
            "removal_request": f"Removal request raised for {worker['name']}.",
        }
        stage_map = {
            "transfer_request": "Waiting for origin approval",
            "status_change": "Location review",
            "removal_request": "Group pastor review",
        }
        row = {
            "request_id": f"req-{next_index:03d}",
            "request_type": request_type,
            "worker_name": worker["name"],
            "worker_id": worker["worker_id"],
            "origin_location": worker["location"],
            "destination_location": payload.get("destination_location", "").strip(),
            "requested_by": requester_name,
            "status": "pending",
            "submitted_at": f"{TODAY.isoformat()} 09:00",
            "current_stage": stage_map[request_type],
            "summary": payload["reason"].strip(),
            "path": worker["path"],
            "timeline": [
                {"label": "Submitted", "state": "done", "note": "Request created and sent for review."},
                {"label": stage_map[request_type], "state": "current", "note": "Waiting for current level review."},
                {"label": "Final decision", "state": "pending", "note": "Approval, rejection, or escalation."},
            ],
            "review_history": [],
            "new_status": payload.get("new_status", "").strip(),
        }
        self.requests.insert(0, row)
        inbox_kind = {
            "transfer_request": "transfer_request",
            "status_change": "status_change",
            "removal_request": "removal_request",
        }[request_type]
        title_map = {
            "transfer_request": "Review transfer request",
            "status_change": "Review status change",
            "removal_request": "Review worker removal request",
        }
        self.inbox.insert(
            0,
            {
                "item_id": f"inbox-{len(self.inbox) + 1:03d}",
                "kind": inbox_kind,
                "title": title_map[request_type],
                "subject": worker["name"],
                "request_id": row["request_id"],
                "worker_id": row["worker_id"],
                "location": worker["location"],
                "path": worker["path"],
                "submitted_at": "Just now",
                "priority": "High" if request_type == "removal_request" else "Medium",
                "current_stage": row["current_stage"],
                "summary": row["summary"],
                "resolved": False,
            },
        )
        self.activity.insert(
            0,
            {
                "message": f"{request_type.replace('_', ' ').title()} created for {worker['name']}",
                "meta": f"{worker['location']} - Just now",
                "tone": "info",
                "path": worker["path"],
            },
        )
        return row

    def act_request(self, request_id: str, action: str, notes: str, actor_name: str) -> dict[str, Any] | None:
        row = self.get_request(request_id)
        if row is None:
            return None
        worker = self.get_worker(row["worker_id"])
        linked_user = self.get_user_by_worker(row["worker_id"])
        if action == "approve":
            row["status"] = "approved"
            row["current_stage"] = "Approved"
            tone = "success"
            timeline_state = "done"
        elif action == "reject":
            row["status"] = "rejected"
            row["current_stage"] = "Rejected"
            tone = "danger"
            timeline_state = "done"
        else:
            row["status"] = "escalated"
            row["current_stage"] = "Escalated to next level"
            tone = "warning"
            timeline_state = "current"
        row["review_history"].insert(
            0,
            {
                "reviewer": actor_name,
                "action": action,
                "note": notes.strip() or "No note added.",
                "time": "Just now",
            },
        )
        if row["timeline"]:
            row["timeline"][-1]["state"] = timeline_state
            row["timeline"][-1]["note"] = row["current_stage"]
        if action == "approve" and worker is not None:
            if row["request_type"] == "transfer_request" and row["destination_location"] in LOCATION_LOOKUP:
                destination = LOCATION_LOOKUP[row["destination_location"]]
                worker["location"] = destination["location"]
                worker["group"] = destination["group"]
                worker["region"] = destination["region"]
                worker["state"] = destination["state"]
                worker["path"] = destination["path"]
                if linked_user is not None:
                    linked_user["location"] = destination["location"]
                    linked_user["path"] = destination["path"]
            elif row["request_type"] == "status_change" and row.get("new_status", ""):
                worker["status"] = row["new_status"]
                if linked_user is not None:
                    normalized_status = row["new_status"].lower()
                    if normalized_status == "active":
                        linked_user["status"] = "active"
                    elif normalized_status == "inactive":
                        linked_user["status"] = "inactive"
                    elif normalized_status == "suspended":
                        linked_user["status"] = "suspended"
            elif row["request_type"] == "removal_request":
                worker["status"] = "Inactive"
                if linked_user is not None:
                    linked_user["status"] = "inactive"
        activity_location = row.get("location") or (worker or {}).get("location") or row.get("destination_location", "Unknown location")
        self.activity.insert(
            0,
            {
                "message": f"{row['request_type'].replace('_', ' ').title()} for {row['worker_name']} was {action}d",
                "meta": f"{activity_location} | Just now",
                "tone": tone,
                "path": row["path"],
            },
        )
        return row

    def list_inbox(self, scope_path: str, kind: str = "all") -> list[dict[str, Any]]:
        rows = [row for row in self.inbox if in_scope(row["path"], scope_path) and not row["resolved"]]
        if kind and kind != "all":
            rows = [row for row in rows if row["kind"] == kind]
        return rows

    def get_inbox_item(self, item_id: str) -> dict[str, Any] | None:
        return next((row for row in self.inbox if row["item_id"] == item_id), None)

    def resolve_inbox_item(self, item_id: str) -> dict[str, Any] | None:
        row = self.get_inbox_item(item_id)
        if row is None:
            return None
        worker = self.get_worker(row.get("worker_id", "")) if row.get("worker_id") else None
        account = self.get_user(row.get("account_id", "")) if row.get("account_id") else None
        linked_request = self.get_request(row.get("request_id", "")) if row.get("request_id") else None
        return {
            "item": row,
            "worker": worker,
            "account": account,
            "request": linked_request,
        }

    def act_inbox_item(self, item_id: str, action: str, notes: str, *, actor_name: str) -> dict[str, Any] | None:
        row = self.get_inbox_item(item_id)
        if row is None:
            return None
        linked_request = self.get_request(row.get("request_id", "")) if row.get("request_id") else None
        linked_user = self.get_user(row.get("account_id", "")) if row.get("account_id") else None
        linked_worker = self.get_worker(row.get("worker_id", "")) if row.get("worker_id") else None
        if linked_request is not None:
            updated_request = self.act_request(linked_request["request_id"], action, notes, actor_name)
            if updated_request is None:
                return None
            row["current_stage"] = updated_request["current_stage"]
            row["summary"] = updated_request["summary"]
        if action == "approve":
            row["resolved"] = True
            row["current_stage"] = "Approved"
            tone = "success"
        elif action == "reject":
            row["resolved"] = True
            row["current_stage"] = "Rejected"
            tone = "danger"
        else:
            row["resolved"] = False
            row["current_stage"] = "Escalated to next level"
            row["submitted_at"] = "Just now"
            tone = "warning"
        row["last_note"] = notes.strip()
        self.activity.insert(
            0,
            {
                "message": f"{row['title']} for {row['subject']} was {action}d",
                "meta": f"{row['location']} | Just now",
                "tone": tone,
                "path": row["path"],
            },
        )
        worker = linked_worker or next(
            (
                item
                for item in self.workers
                if item["name"] == row["subject"] and item["location"] == row["location"]
            ),
            None,
        )
        if worker and row["kind"] == "worker_registration" and action == "approve":
            worker["approval_status"] = "approved"
            worker["status"] = "Active"
        elif worker and row["kind"] == "worker_registration" and action == "reject":
            worker["approval_status"] = "rejected"
            worker["status"] = "Inactive"
        if linked_user and row["kind"] == "user_approval":
            if action == "approve":
                linked_user["approval_status"] = "approved"
                linked_user["status"] = "active"
            elif action == "reject":
                linked_user["approval_status"] = "rejected"
                linked_user["status"] = "inactive"
        return row

    def recent_activity(self, scope_path: str) -> list[dict[str, Any]]:
        return [row for row in self.activity if in_scope(row["path"], scope_path)][:6]

    def counts_summary(self, scope_path: str) -> dict[str, Any]:
        rows = self.list_counts(scope_path)
        if not rows:
            return {"monthly_total": 0, "latest_total": 0, "locations_reporting": 0, "average_total": 0}
        latest = rows[0]
        monthly_total = sum(row["total"] for row in rows if row["date"].startswith("2026-03"))
        return {
            "monthly_total": monthly_total,
            "latest_total": latest["total"],
            "locations_reporting": len({row["location"] for row in rows}),
            "average_total": int(sum(row["total"] for row in rows) / len(rows)),
        }

    def dashboard_summary(self, scope_path: str, level: int) -> dict[str, Any]:
        workers = self.list_workers(scope_path)
        counts = self.list_counts(scope_path)
        inbox = self.list_inbox(scope_path)
        latest_total = counts[0]["total"] if counts else 0
        return {
            "workers_total": len(workers),
            "pending_items": len(inbox),
            "pending_workers": sum(1 for row in workers if row["approval_status"] == "pending_verification"),
            "last_count_total": latest_total,
            "locations_in_view": len({row["location"] for row in workers}) or len(self.visible_locations(scope_path)),
            "level": level,
        }

    def scope_breakdown(self, scope_path: str, *, group_by: str) -> list[dict[str, Any]]:
        bucket: dict[str, dict[str, Any]] = {}
        for row in self.list_counts(scope_path):
            key = row[group_by]
            bucket.setdefault(key, {"label": key, "total": 0, "counts": 0, "location_count": set()})
            bucket[key]["total"] += row["total"]
            bucket[key]["counts"] += 1
            bucket[key]["location_count"].add(row["location"])

        pending_map: dict[str, int] = {}
        for item in self.list_inbox(scope_path):
            pending_map[item["location"]] = pending_map.get(item["location"], 0) + 1

        rows = []
        for label, values in bucket.items():
            rows.append(
                {
                    "label": label,
                    "total": values["total"],
                    "counts": values["counts"],
                    "locations": len(values["location_count"]),
                    "pending": pending_map.get(label, 0),
                }
            )
        return sorted(rows, key=lambda row: row["total"], reverse=True)


STORE = DemoStore()
