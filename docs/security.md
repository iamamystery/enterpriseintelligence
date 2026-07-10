# ETIP Security

## Password storage

`app/core/security.py` hashes passwords with `bcrypt` directly (not via
`passlib`): `bcrypt.hashpw(password, bcrypt.gensalt())`. Verification is a
constant-time `bcrypt.checkpw`. Passwords are validated at the schema layer
(`UserRegister`/`UserCreate`) to be 8–128 characters; there's no additional
complexity requirement (uppercase/digit/symbol) enforced.

## Authentication: JWT access + refresh tokens

Stateless, symmetric-key JWTs (`PyJWT`, `HS256`), signed with
`settings.JWT_SECRET_KEY`. Two token types, distinguished by a `type` claim:

- **Access token** (`create_access_token`) — `{"sub": user_id, "exp": ...,
  "type": "access"}`, expires after `ACCESS_TOKEN_EXPIRE_MINUTES` (default
  30 min). Required on every authenticated request via
  `Authorization: Bearer <token>`.
- **Refresh token** (`create_refresh_token`) — same shape but
  `"type": "refresh"`, expires after `REFRESH_TOKEN_EXPIRE_DAYS` (default 7
  days). Only accepted at `POST /api/v1/auth/refresh`.

`get_current_user` (`app/api/dependencies/auth.py`) decodes the bearer token,
rejects it if `type != "access"` (so a leaked refresh token can't be used
directly as an access token against protected routes), loads the `User` by
the `sub` claim, and rejects inactive users. `AuthService.refresh` performs
the mirror-image check for `type != "refresh"`.

**Points worth knowing**:
- Tokens are **not revocable** — there is no blacklist/denylist or token
  version stored on the user. A leaked access token is valid until it
  naturally expires (30 min by default); a leaked refresh token is valid for
  up to 7 days. Logout, password change, and role/permission changes do not
  invalidate already-issued tokens.
- Refresh does not rotate/invalidate the previous refresh token (no reuse
  detection) — presenting the same still-valid refresh token twice will
  happily issue two new token pairs.
- `JWT_SECRET_KEY` is a single symmetric secret shared by every environment
  that needs to issue or verify tokens. It must be set to a strong random
  value outside local dev (`.env.example` ships `changeme`, and CI uses a
  clearly-labeled test-only value) — anyone with this secret can forge valid
  tokens for any user ID.

## Authorization: role-based permission strings

`Role.permissions` is a flat Postgres string array (e.g. `["*"]`,
`["vulnerabilities:read", "users:manage"]`) — there's no separate
permissions table or hierarchy, just string membership checks.
`require_permission(permission)` (`app/api/dependencies/permissions.py`) is a
dependency factory: it allows `is_superuser` users through unconditionally,
otherwise requires `"*"` or the exact permission string to be present on the
current user's role, else `403`.

The `admin` role is created automatically on first registration with
`permissions: ["*"]` (see the registration flow below); the wildcard grants
every permission check. Other roles (e.g. `analyst`) can now be created via
`POST /api/v1/roles` (requires `roles:manage`) and referenced by name when
an admin creates a user via `POST /api/v1/users`.

Because permissions are just strings checked at each endpoint via
`require_permission("resource:action")`, adding a new protected capability
means picking a permission string, calling `require_permission(...)` in the
route, and making sure roles are granted that string — there's no central
permission registry enforcing that route permissions and role permissions
stay in sync.

**Roles are global, not per-organization.** `Role` has no
`organization_id` — it's a system-wide table, so `POST /api/v1/roles`
creates a role visible to and assignable by every organization, not just
the caller's. Combined with the wildcard permission model, this means any
org's `admin` (`permissions: ["*"]`) can create or rename roles that affect
every other tenant in the system — there's no tenant boundary on role
management today. This is a pre-existing property of the data model (the
`admin` role created at registration was already global before role
management had an API), not something introduced by adding the endpoint,
but it's worth fixing (e.g. scoping `Role` to an organization, or
restricting `roles:manage` to a genuine superuser) before this is exposed
to untrusted tenants.

**`search:read` is a coarse, standalone permission.**
`GET /api/v1/search` (`app/api/v1/endpoints/search.py`) returns matches
across vulnerabilities, advisories, *and* assets in one response, but is
gated by a single `search:read` permission — not by the individual
`vulnerabilities:read`/`advisories:read`/`assets:read` permissions that
gate those resources' own endpoints. A user granted `search:read` alone
(without any of the other three) can still see vulnerability, advisory,
and asset matches through search. This is a deliberate simplification
(matching the one-permission-per-endpoint pattern used everywhere else)
rather than per-type permission filtering within a single response. Asset
results are still always scoped to the caller's own organization — that
tenant boundary is enforced unconditionally, independent of any
permission check — but if you want search access to strictly imply
possessing the corresponding per-type read permission, that would need to
be enforced explicitly (e.g. checking `current_user.role.permissions` per
type before including that group in the response), which isn't done today.

## Registration flow: self-service registration only creates new organizations

`AuthService.register` (`app/services/auth_service.py`) slugifies
`data.organization_name` and calls `OrganizationRepository.get_by_slug`
first. If an organization with that slug already exists, registration is
**rejected** with `409 AlreadyExistsError` ("An organization named '...'
already exists. Ask an administrator of that organization to create an
account for you.") — self-registration never joins an existing
organization, and it never grants admin access on one. A new `Organization`
row (and its first `admin` user, with `permissions: ["*"]`) is only created
when the slugified name is unused.

Joining an *existing* organization is only possible via the admin-only
`POST /api/v1/users` endpoint (`users:manage` permission required), which
adds the new user to the requesting admin's own `organization_id` — so
membership in an existing org always requires action by one of its current
admins, never just knowing/guessing its name.

Covered by `test_register_rejects_duplicate_organization_name` and
`test_register_rejects_organization_name_that_slugifies_to_existing_slug` in
`tests/services/test_auth_service.py` (the latter checks that names which
differ only in case/punctuation/whitespace, e.g. `"Shared Org!!"` vs.
`"  shared   org  "`, both resolve to the same slug and are still rejected).

## Rate limiting

`app/api/dependencies/rate_limit.py` implements `InMemoryRateLimiter`, a
sliding 60-second window per client key (`request.client.host` — the raw
socket IP, with no `X-Forwarded-For`/`X-Real-IP` handling, so behind a proxy
or load balancer every request may appear to come from the same IP unless
the proxy preserves the real client address some other way). Two limiter
instances are applied at the router level via `Depends`:

- General API routes: `RATE_LIMIT_PER_MINUTE` (default 60/min)
- `/auth/*` routes: `AUTH_RATE_LIMIT_PER_MINUTE` (default 5/min) — a
  stricter limit intended to slow down credential-stuffing/brute-force
  attempts against login/register/refresh

State is held in process memory (a `defaultdict(list)` of timestamps), so
limits are **per app instance**, not shared across replicas — running
multiple `app` containers behind a load balancer effectively multiplies the
real limit by the replica count. There's no persistence, so limits reset on
restart/redeploy.

## CORS

`CORSMiddleware` is registered in `app/main.py` with
`allow_origins=settings.CORS_ORIGINS` (default
`["http://localhost:3000"]`), `allow_credentials=True`,
`allow_methods=["*"]`, `allow_headers=["*"]`. In any real deployment,
`CORS_ORIGINS` must be set to the actual frontend origin(s) — the default is
dev-only. `allow_credentials=True` combined with a wildcard origin would be
rejected by browsers anyway (CORS spec forbids `*` + credentials), so
`CORS_ORIGINS` must always be an explicit origin list, never `["*"]`.

## Error responses and information disclosure

Domain errors (`app/core/exceptions.py`: `NotFoundError`,
`AlreadyExistsError`, `AuthenticationError`, `AuthorizationError`,
`ValidationError`, `ScraperError`) are mapped to `{"detail": message}` with
an appropriate status code by a single handler
(`app/core/exception_handlers.py`). `AuthenticationError` messages
(`"Invalid email or password"`, `"User account is disabled"`) are
deliberately generic and don't distinguish "no such user" from "wrong
password", which avoids leaking whether a given email is registered.
Uncaught exceptions are now caught by `ErrorHandlingMiddleware`
(`app/core/middleware/error_handling.py`), which logs the exception (with
traceback, via the `app.error` logger) and returns a generic
`{"detail": "Internal server error"}` 500 — no exception type, message, or
traceback is ever included in the response body, regardless of `DEBUG`. See
`docs/architecture.md` ("Custom middleware") for how this composes with the
existing `ETIPError` handler.

## Secrets and environment

Sensitive configuration (`JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, Mongo root
credentials) is read from environment variables / `.env`, which is
gitignored. Only `.env.example` (placeholder values) is committed. See
`docs/deployment.md` for the full variable list.

## Known gaps

- No token revocation/blacklist mechanism.
- No refresh-token rotation or reuse detection.
- Rate limiting and scheduled jobs are both process-local, not
  replica-safe (see `docs/deployment.md`).
- No audit logging — `AuditLog` model and `audit_repository.py` are empty
  stubs; sensitive actions (login, permission changes, user creation) are
  not currently recorded anywhere queryable.
- No account lockout after repeated failed logins beyond the general auth
  rate limit.
- No invite-token system yet — adding a user to an existing organization
  requires an existing admin to do it via `POST /api/v1/users`; there's no
  self-service "request to join" or email-verified invite link flow.
- Roles are global, not tenant-scoped — any organization's `admin` can
  create/see roles that affect every other organization via
  `POST /api/v1/roles` (see "Roles are global" above).
