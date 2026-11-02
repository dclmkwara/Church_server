# Security and Access Control

## Authentication

- API requests use signed JWT bearer tokens.
- Access tokens expire after the configured `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 60 minutes).
- Refresh tokens are stored by JTI, expire after the configured refresh period (default: 30 days), and are rotated on use. The backend rejects refresh-type tokens on protected API routes and atomically claims a refresh token before rotation.
- Passwords use bcrypt. Password inputs are limited to 72 UTF-8 bytes to avoid bcrypt truncation; users with older longer passwords may need a reset.
- Password reset tokens are consumed once and password changes revoke persisted refresh tokens. Self-service reset email delivery is not implemented, so the reset endpoint is not operational as a user recovery channel until delivery is configured.
- Access JWTs are stateless and are not revoked on password changes; they remain usable until expiry. There is no logout-all mechanism.

## Authorization

- Each user can have multiple roles; the highest role score determines the maximum hierarchical scope.
- Role scores and the user's current path are reloaded for protected requests so role or path changes take effect without waiting for a token refresh.
- Route permissions and hierarchical `ltree` filters are enforced in application code.
- PostgreSQL RLS is enabled on every public application table, with 98 policies installed by migration `e41a8b9c7d6f`. Scoped tables fail closed when request context is absent; public intake permits inserts only, and shared lookup tables are read-only for ordinary users.
- API database traffic uses the dedicated `church_app_runtime` role (`NOSUPERUSER`, `NOBYPASSRLS`, no database/role creation privileges). The privileged migration connection is kept separately in `SYNC_DATABASE_URL` and is not used by API requests.
- Direct PostgreSQL checks with the runtime role verified zero unscoped location rows, scoped visibility surviving commits, self-account/role lookup, and shared lookup visibility. Hosted deployment credentials still need to be changed to this least-privilege role before deployment; local `.env` credentials are not deployed automatically.
- Level 8 access is bounded by the user's home continent and the nations resolved within that continent.

## Browser Access

- `BACKEND_CORS_ORIGINS` must list exact frontend origins. An unset value denies cross-origin browser access; wildcard origins are rejected.
- Configure proxy trust and client-IP forwarding only at the deployment edge. The in-process rate limiter uses the request's client address and is not shared across workers or replicas.

## Known Security and Operations Gaps

- Login and password-reset throttles are process-local. Use shared gateway controls or a shared store before multi-replica deployment.
- Configure and verify a secure password-reset delivery channel and frontend reset URL before enabling self-service recovery.
- Define a logout-all and access-token revocation approach if immediate session termination is required.
- Verify scheduler and materialized-view refresh alerts, database backup/restore, and deployment secret handling in the target environment.
- The runtime dependency set still needs a reproducible lock and isolated API/UI dependency resolution before deployment.
