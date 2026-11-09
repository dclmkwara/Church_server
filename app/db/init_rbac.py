from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import Role, Permission, RoleScore
from app.crud.crud_rbac import role, permission as crud_permission
from app.schemas.rbac import RoleCreate, PermissionCreate

def _perm(permission: str, name: str, description: str) -> dict[str, str]:
    return {"permission": permission, "name": name, "description": description}


# Define all system permissions used by the route layer.
# Keep this list aligned with PermissionChecker(...) usages.
DEFAULT_PERMISSIONS = [
    # Users
    _perm("users:create", "Create User", "Can create application user accounts"),
    _perm("users:read", "Read Users", "Can view application user accounts"),
    _perm("users:update", "Update User", "Can edit application user accounts"),
    _perm("users:delete", "Delete User", "Can delete application user accounts"),
    _perm("users:approve", "Approve User", "Can approve or reject user access requests"),
    _perm("users:assign_roles", "Assign User Roles", "Can assign roles to users"),
    _perm("users:deactivate", "Deactivate User", "Can deactivate user accounts"),

    # Workers
    _perm("workers:create", "Create Worker", "Can register workers"),
    _perm("workers:read", "Read Workers", "Can view workers"),
    _perm("workers:update", "Update Worker", "Can edit worker records"),
    _perm("workers:delete", "Delete Worker", "Can remove worker records"),
    _perm("workers:approve", "Approve Worker", "Can approve worker registrations"),
    _perm("workers:request_changes", "Request Worker Changes", "Can prepare worker transfer, removal, and status-change requests"),

    # Programs
    _perm("programs:read", "Read Programs", "Can view program domains, types, and events"),
    _perm("programs:manage", "Manage Programs", "Can create, update, and delete program domains, types, and events"),
    _perm("programs:create_event", "Create Program Events", "Can schedule program events within the assigned jurisdiction"),
    _perm("programs:assign_workers", "Assign Event Workers", "Can assign officiating workers to special program events"),
    _perm("programs:approve_assignments", "Approve Event Assignments", "Can approve or reject officiating worker assignments for special program events"),
    _perm("programs:approve_events", "Approve Program Events", "Can approve or reject event schedules at the assigned level"),

    # Officials / appointments
    _perm("officials:read", "Read Official Appointments", "Can view official appointments within scope"),
    _perm("officials:manage", "Manage Official Appointments", "Can create, update, and revoke official appointments"),

    # Counts
    _perm("counts:create", "Create Count", "Can submit attendance counts"),
    _perm("counts:read", "Read Counts", "Can view attendance counts"),
    _perm("counts:update", "Update Count", "Can edit attendance counts"),
    _perm("counts:delete", "Delete Count", "Can delete attendance counts"),
    _perm("counts:review", "Review Program Counts", "Can approve or reject count submissions within the assigned reporting level"),
    _perm("counts:remind", "Remind Reporting Locations", "Can send a Sunday reporting reminder to eligible users at a location within scope"),

    # Offerings and tithes
    _perm("offerings:create", "Create Offering", "Can record offerings and tithes"),
    _perm("offerings:read", "Read Offerings", "Can view offerings and tithes"),
    _perm("offerings:update", "Update Offering", "Can edit offerings and tithes"),
    _perm("offerings:review", "Review Offering", "Can approve or reject offering and tithe entries within scope"),
    _perm("offerings:delete", "Delete Offering", "Can delete offerings and tithes"),

    # Records / follow-up
    _perm("records:create", "Create Records", "Can create newcomers, converts, and member records"),
    _perm("records:read", "Read Records", "Can view newcomers, converts, and member records"),
    _perm("records:update", "Update Records", "Can update newcomers, converts, and member records"),
    _perm("records:delete", "Delete Records", "Can delete newcomers, converts, and member records"),

    # Attendance
    _perm("attendance:create", "Create Attendance", "Can mark worker attendance"),
    _perm("attendance:read", "Read Attendance", "Can view worker attendance"),
    _perm("attendance:update", "Update Attendance", "Can edit worker attendance"),
    _perm("attendance:delete", "Delete Attendance", "Can delete worker attendance"),

    # Fellowship
    _perm("fellowship:create", "Create Fellowship Activity", "Can create fellowship records"),
    _perm("fellowship:read", "Read Fellowship Activity", "Can view fellowship records"),
    _perm("fellowship:update", "Update Fellowship Activity", "Can edit fellowship records"),
    _perm("fellowship:delete", "Delete Fellowship Activity", "Can delete fellowship records"),

    # Announcements / information
    _perm("announcements:read", "Read Announcements", "Can view announcements and weekly information"),
    _perm("announcements:manage", "Manage Announcements", "Can create, update, publish, and deactivate announcements"),

    # Organization / hierarchy
    _perm("hierarchy:update", "Update Nations", "Can update nation records"),
    _perm("hierarchy:delete", "Delete Nations", "Can delete nation records"),
    _perm("hierarchy:create_nation", "Create Nations", "Can create nations"),
    _perm("hierarchy:create_state", "Create States", "Can create states"),
    _perm("hierarchy:update_state", "Update States", "Can update states"),
    _perm("hierarchy:delete_state", "Delete States", "Can delete states"),
    _perm("hierarchy:create_region", "Create Regions", "Can create regions"),
    _perm("hierarchy:update_region", "Update Regions", "Can update regions"),
    _perm("hierarchy:delete_region", "Delete Regions", "Can delete regions"),
    _perm("hierarchy:create_group", "Create Groups", "Can create groups"),
    _perm("hierarchy:update_group", "Update Groups", "Can update groups"),
    _perm("hierarchy:delete_group", "Delete Groups", "Can delete groups"),
    _perm("hierarchy:create_location", "Create Locations", "Can create locations"),
    _perm("hierarchy:update_location", "Update Locations", "Can update locations"),
    _perm("hierarchy:delete_location", "Delete Locations", "Can delete locations"),
    _perm("hierarchy:create_fellowship", "Create Fellowships", "Can create fellowships"),
    _perm("hierarchy:update_fellowship", "Update Fellowships", "Can update fellowships"),
    _perm("hierarchy:delete_fellowship", "Delete Fellowships", "Can delete fellowships"),

    # Reports and statistics
    _perm("reports:read", "Read Reports", "Can view reports"),
    _perm("reports:refresh", "Refresh Reports", "Can refresh report materializations"),
    _perm("statistics:read", "Read Statistics", "Can view statistics endpoints"),
    _perm("population_estimates:manage", "Manage Expected Population", "Can set versioned expected Sunday attendance within the assigned State"),

    # Notifications and media
    _perm("notifications:read", "Read Notifications", "Can poll notifications"),
    _perm("media:read", "Read Media", "Can view media galleries and items"),
    _perm("media:create_gallery", "Create Media Galleries", "Can create media galleries"),
    _perm("media:create_item", "Create Media Items", "Can upload media items"),
    _perm("media:delete_gallery", "Delete Media Galleries", "Can delete media galleries"),
    _perm("media:delete_item", "Delete Media Items", "Can delete media items"),

    # Sync / operations
    _perm("sync:batch", "Run Batch Sync", "Can submit batch sync operations"),
    _perm("sync:read_changes", "Read Sync Changes", "Can read sync change feeds"),
    _perm("sync:conflicts", "Review Sync Conflicts", "Can review sync conflicts"),
    _perm("sync:resolve", "Resolve Sync Conflicts", "Can resolve sync conflicts"),

    # System / RBAC
    _perm("rbac:read", "Read RBAC", "Can view roles, permissions, and score mappings"),
    _perm("rbac:manage", "Manage RBAC", "Can manage roles, permissions, and score mappings"),
    _perm("system:read_audit_logs", "Read Audit Logs", "Can view audit logs"),
    _perm("system:read_public_intake", "Read Public Intake", "Can review public contact and prayer submissions"),
    _perm("system:manage_public_intake", "Manage Public Intake", "Can mark public contact and prayer submissions as reviewed"),
    _perm("system:seed", "Run Seed Utilities", "Can run administrative seed utilities"),
]

# Common permission groups
BASE_READ = [
    "workers:read",
    "users:read",
    "programs:read",
    "counts:read",
    "offerings:read",
    "records:read",
    "attendance:read",
    "fellowship:read",
    "announcements:read",
    "notifications:read",
]

REPORTING_READ = ["reports:read", "statistics:read"]

DATA_ENTRY_PERMS = [
    "counts:create",
    "counts:update",
    "offerings:create",
    "offerings:update",
    "records:create",
    "records:update",
    "attendance:create",
    "attendance:update",
    "fellowship:create",
    "fellowship:update",
]

DATA_DELETE_PERMS = [
    "counts:delete",
    "offerings:delete",
    "records:delete",
    "attendance:delete",
    "fellowship:delete",
]

MEDIA_PERMS = [
    "media:read",
    "media:create_gallery",
    "media:create_item",
    "media:delete_gallery",
    "media:delete_item",
]

OFFICIAL_PERMS = [
    "officials:read",
    "officials:manage",
]

USHER_PERMS = BASE_READ + DATA_ENTRY_PERMS + ["sync:batch"]

ADMIN_PERMS = USHER_PERMS + [
    "users:create",
    "users:update",
    "workers:create",
    "workers:update",
    "programs:manage",
] + REPORTING_READ + ["counts:remind", "workers:request_changes"]

PASTOR_PERMS = ADMIN_PERMS + DATA_DELETE_PERMS + REPORTING_READ + [
    "offerings:review",
    "users:approve",
    "users:delete",
    "users:deactivate",
    "workers:approve",
    "workers:delete",
    "announcements:manage",
    "reports:refresh",
    "rbac:read",
    "programs:approve_events",
]

# A Location Pastor can suspend a worker and request removal, but cannot
# permanently remove the worker directly. Group leadership and above retain
# the workers:delete action through the approved removal flow.
LOCATION_PASTOR_PERMS = [p for p in PASTOR_PERMS if p != "workers:delete"]

REGION_HIERARCHY_PERMS = [
    "hierarchy:create_group",
    "hierarchy:update_group",
    "hierarchy:create_location",
    "hierarchy:update_location",
    "hierarchy:create_fellowship",
    "hierarchy:update_fellowship",
    "hierarchy:update_region",
]

STATE_HIERARCHY_PERMS = REGION_HIERARCHY_PERMS + [
    "hierarchy:create_region",
    "hierarchy:delete_region",
    "hierarchy:delete_group",
    "hierarchy:delete_location",
    "hierarchy:delete_fellowship",
    "hierarchy:update_state",
]

NATIONAL_HIERARCHY_PERMS = STATE_HIERARCHY_PERMS + [
    "hierarchy:create_state",
    "hierarchy:delete_state",
]

# Higher leadership uses the same shared backend. These grants preserve the
# operational authority above state level; request and RLS scope still limits
# each action to the user's national or continental jurisdiction. RBAC catalog
# mutation and seed utilities remain reserved to score 9.
HIGHER_ADMIN_PERMS = [
    p["permission"] for p in DEFAULT_PERMISSIONS
    if p["permission"] not in {"rbac:manage", "system:seed"}
]

# Define in-scope roles plus read-only placeholders for reserved enterprise levels.
DEFAULT_ROLES = {
    # House Caring Fellowship is location-scoped and separate from the main program spine.
    "House Fellowship Leader": {
        "score_id": 1,
        "permissions": ["fellowship:create", "fellowship:read", "fellowship:update", "sync:batch"]
    },

    # Level 1: Field worker / usher (field data capture only).
    # A location worker is the designated field data collector in the Utility App.
    # Batch uploads remain constrained by the worker's assigned location scope.
    "Location Worker": {"score_id": 1, "permissions": BASE_READ + ["sync:batch"]},
    "Location Usher": {"score_id": 1, "permissions": USHER_PERMS},

    # Level 2: Location governance
    "Location Admin": {"score_id": 2, "permissions": ADMIN_PERMS + ["programs:create_event"]},
    "Location Pastor": {"score_id": 2, "permissions": LOCATION_PASTOR_PERMS + ["users:assign_roles", "programs:create_event"]},

    # Level 1: collection role at the group scope; not group governance.
    "Group Usher": {"score_id": 1, "permissions": USHER_PERMS},

    # Level 3: group governance
    "Group Admin": {"score_id": 3, "permissions": ADMIN_PERMS + ["programs:create_event", "programs:assign_workers", "programs:approve_assignments"] + OFFICIAL_PERMS},
    "Group Pastor": {"score_id": 3, "permissions": PASTOR_PERMS + ["counts:review", "counts:remind", "users:assign_roles", "programs:create_event", "programs:assign_workers", "programs:approve_assignments"] + OFFICIAL_PERMS},

    # Level 1: collection role at the region scope; not region governance.
    "Region Usher": {"score_id": 1, "permissions": USHER_PERMS},

    # Level 4: region governance
    "Region Admin": {
        "score_id": 4,
        "permissions": ADMIN_PERMS + ["programs:create_event", "programs:assign_workers", "programs:approve_assignments"] + OFFICIAL_PERMS + REGION_HIERARCHY_PERMS
    },
    "Region Pastor": {
        "score_id": 4,
        "permissions": PASTOR_PERMS + ["counts:review", "users:assign_roles", "programs:create_event", "programs:assign_workers", "programs:approve_assignments"] + OFFICIAL_PERMS + REGION_HIERARCHY_PERMS
    },

    # Level 1: event capture role. Event-specific Alpha access must be granted
    # through an approved event assignment rather than a high global score.
    "State Usher": {"score_id": 1, "permissions": USHER_PERMS},

    # Level 5: state governance
    "State Admin": {
        "score_id": 5,
        "permissions": ADMIN_PERMS + ["population_estimates:manage", "programs:create_event", "programs:assign_workers", "programs:approve_assignments"] + OFFICIAL_PERMS + STATE_HIERARCHY_PERMS
    },
    "State Overseer": {
        "score_id": 5,
        "permissions": PASTOR_PERMS + ["counts:review", "users:assign_roles", "population_estimates:manage", "programs:create_event", "programs:assign_workers", "programs:approve_assignments"] + OFFICIAL_PERMS + STATE_HIERARCHY_PERMS
    },

    # Enterprise roles are seeded for the separate higher-level client, which
    # shares this backend. Their authority remains explicitly scoped by score.
    "Zonal Coordinator": {"score_id": 6, "permissions": HIGHER_ADMIN_PERMS},

    # Level 7: National Governance
    "National Admin": {
        "score_id": 7,
        "permissions": HIGHER_ADMIN_PERMS
    },
    "National Overseer": {
        "score_id": 7,
        "permissions": HIGHER_ADMIN_PERMS
    },

    # Level 8: Continental Governance
    "Continental Admin": {
        "score_id": 8,
        "permissions": HIGHER_ADMIN_PERMS,
    },
    "Continental Overseer": {
        "score_id": 8,
        "permissions": HIGHER_ADMIN_PERMS,
    },

    # Level 9: Global Governance
    "Global Admin": {
        "score_id": 9,
        "permissions": [p["permission"] for p in DEFAULT_PERMISSIONS]
    },
}

SCORE_NAMES = {
    1: "Church Worker / Usher",
    2: "Location Pastor",
    3: "Group Pastor",
    4: "Regional Pastor",
    5: "State Pastor / Overseer",
    6: "Zonal Coordinator",
    7: "National Overseer",
    8: "Continental Leader",
    9: "General Overseer / Global Admin"
}

async def init_rbac(db: AsyncSession):
    """Seed default roles, permissions, and score levels."""
    print("Seeding DCLM RBAC structure...")

    # 1. Seed Permissions
    created_perms = {}
    for perm_data in DEFAULT_PERMISSIONS:
        stmt = select(Permission).where(Permission.permission == perm_data["permission"])
        existing = (await db.execute(stmt)).scalars().first()

        if not existing:
            print(f"  Creating permission: {perm_data['permission']}")
            p_in = PermissionCreate(
                permission=perm_data["permission"],
                name=perm_data["name"],
                description=perm_data["description"]
            )
            existing = await crud_permission.create(db, obj_in=p_in)
        else:
            changed = False
            if existing.name != perm_data["name"]:
                existing.name = perm_data["name"]
                changed = True
            if existing.description != perm_data["description"]:
                existing.description = perm_data["description"]
                changed = True
            if changed:
                print(f"  Updating permission metadata: {perm_data['permission']}")
                db.add(existing)

        created_perms[existing.permission] = existing.id

    await db.commit()

    # 2. Seed Role Scores (1-9)
    for score_val, name in SCORE_NAMES.items():
        stmt = select(RoleScore).where(RoleScore.score == score_val)
        existing = (await db.execute(stmt)).scalars().first()
        if not existing:
             print(f"  Creating RoleScore: {score_val} ({name})")
             new_score = RoleScore(score=score_val, score_name=name)
             db.add(new_score)
             await db.commit()
             await db.refresh(new_score)
        elif existing.score_name != name:
            existing.score_name = name
            db.add(existing)

    await db.commit()

    # 3. Seed Roles
    for role_name, data in DEFAULT_ROLES.items():
        stmt = select(Role).where(Role.role_name == role_name)
        existing_role = (await db.execute(stmt)).scalars().first()

        # Get actual DB score ID for the given score integer
        score_stmt = select(RoleScore).where(RoleScore.score == data["score_id"])
        db_score = (await db.execute(score_stmt)).scalars().first()
        if not db_score:
            print(f"  ERROR: Score {data['score_id']} not found in DB. Skipping role {role_name}")
            continue

        perm_ids = list(dict.fromkeys(created_perms[p] for p in data["permissions"] if p in created_perms))

        if not existing_role:
            print(f"  Creating role: {role_name} (Level {data['score_id']})")
            r_in = RoleCreate(
                role_name=role_name,
                description=f"DCLM {role_name}",
                score_id=db_score.id,
                permission_ids=perm_ids
            )
            await role.create_with_permissions(db, obj_in=r_in)
        else:
            print(f"  Role {role_name} exists, updating permissions (Level {data['score_id']})...")
            # Update score and permissions
            r_in = RoleCreate(
                role_name=role_name,
                description=existing_role.description or f"DCLM {role_name}",
                score_id=db_score.id,
                permission_ids=perm_ids
            )
            await role.update_with_permissions(db, db_obj=existing_role, obj_in=r_in)

    print("RBAC Seeding Complete.")
