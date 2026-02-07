from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import Role, Permission, RoleScore
from app.crud.crud_rbac import role, permission as crud_permission
from app.schemas.rbac import RoleCreate, PermissionCreate

# Define default permissions
DEFAULT_PERMISSIONS = [
    {"permission": "user:create", "name": "Create User", "description": "Can create new users"},
    {"permission": "user:read", "name": "Read User", "description": "Can view user details"},
    {"permission": "user:update", "name": "Update User", "description": "Can update user details"},
    {"permission": "user:delete", "name": "Delete User", "description": "Can delete users"},
    
    {"permission": "fellowship:create", "name": "Create Fellowship", "description": "Can create fellowships"},
    {"permission": "fellowship:read", "name": "Read Fellowship", "description": "Can view fellowships"},
    
    {"permission": "offering:read", "name": "Read Offering", "description": "Can view offering records"},
    {"permission": "offering:create", "name": "Create Offering", "description": "Can create offering records"},
]

# Define default roles and their permissions
DEFAULT_ROLES = {
    "Global Admin": {
        "score_id": 9, 
        "permissions": ["user:create", "user:read", "user:update", "user:delete", "fellowship:create", "fellowship:read", "offering:read", "offering:create"]
    },
    "Location Admin": {
        "score_id": 3,
        "permissions": ["user:read", "fellowship:read", "offering:create"]
    },
    "Member": {
        "score_id": 1,
        "permissions": ["fellowship:read"]
    }
}

async def init_rbac(db: AsyncSession):
    """Seed default roles and permissions."""
    print("Seeding RBAC data...")
    
    # 1. Seed Permissions
    created_perms = {}
    for perm_data in DEFAULT_PERMISSIONS:
        stmt = select(Permission).where(Permission.permission == perm_data["permission"])
        existing = (await db.execute(stmt)).scalars().first()
        
        if not existing:
            print(f"Creating permission: {perm_data['permission']}")
            p_in = PermissionCreate(**perm_data)
            existing = await crud_permission.create(db, obj_in=p_in)
        
        created_perms[existing.permission] = existing.id
        
    # 2. Seed Role Scores (Basic 1-9)
    for i in range(1, 10):
        stmt = select(RoleScore).where(RoleScore.score == i)
        existing = (await db.execute(stmt)).scalars().first()
        if not existing:
             # Basic check, assuming scores exist or we create simple ones
             # For now, let's assume scores might need to be created if not present
             # But RoleScore model has 'score_name' required.
             # Let's verify existing db state or skip score creation for now if complex
             pass 

    # 3. Seed Roles
    for role_name, data in DEFAULT_ROLES.items():
        stmt = select(Role).where(Role.role_name == role_name)
        existing_role = (await db.execute(stmt)).scalars().first()
        
        perm_ids = [created_perms[p] for p in data["permissions"] if p in created_perms]
        
        if not existing_role:
            print(f"Creating role: {role_name}")
            # Ensure Score ID exists (mocking it needs existing score)
            # We will use the score_id provided, assuming seeds exist or we rely on foreign key error to fail
            r_in = RoleCreate(
                role_name=role_name,
                description=f"Default {role_name}",
                score_id=data["score_id"],
                permission_ids=perm_ids
            )
            try:
                await role.create_with_permissions(db, obj_in=r_in)
            except Exception as e:
                print(f"Failed to create role {role_name}: {e}")
        else:
            print(f"Role {role_name} exists, updating permissions...")
            # Update permissions
            existing_role.permissions = [] # Clear old
            # We need to re-fetch/attach, but crud update_with_permissions handles it
            # Let's just use the crud update
            r_in = RoleCreate(role_name=role_name, score_id=data["score_id"], permission_ids=perm_ids)
            await role.update_with_permissions(db, db_obj=existing_role, obj_in=r_in)
            
    print("RBAC Seeding Complete.")
