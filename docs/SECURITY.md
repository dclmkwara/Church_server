# Security and Access Control

## Authentication
- JWT-based auth with refresh tokens.
- Tokens embed role score and scope path.

## RBAC + Role Score
Each user can have multiple roles. The **highest score** defines maximum scope.

### Role Score Semantics
- 1–2: Worker/Usher (location-level scope)
- 3: Location Pastor
- 4: Group Pastor
- 5: Regional Pastor
- 6: State Pastor
- 7: National Admin
- 8: Continental Leader
- 9: Global Admin

### Action Scope
- A user can only assign roles with scores **below** their max score.
- All reads/writes are scoped by `path`.

## Row-Level Control (ltree)
- All scoped entities use `path` and are filtered by `path <@ :scope_path`.
- This means users see only data in their subtree.

## Permission Enforcement
Routes use `PermissionChecker("<resource>:<action>")`.

## Recommendations
- Replace `allow_origins=["*"]` in production.
- Rotate JWT secrets and enforce HTTPS.
