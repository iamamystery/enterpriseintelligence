# ETIP API Reference

All routes below are implemented and mounted today. A few endpoint modules
(`advisories`, `assets`, `search`) still exist as empty files under
`app/api/v1/endpoints/` and are not wired into the router yet — they are not
documented here since they return nothing (they don't exist as routes at
all).

Base URL: `/api/v1` (from `settings.API_V1_PREFIX`), plus one unversioned
route (`/health`).

## Conventions

- **Auth**: Bearer JWT in the `Authorization: Bearer <token>` header, required
  on every route except `/auth/register`, `/auth/login`, `/auth/refresh`, and
  `/health`.
- **Errors**: JSON body `{"detail": "<message>"}` with a matching HTTP status
  (404 not found, 409 already exists, 401 authentication, 403 authorization,
  422 validation, 429 rate limited, 502 upstream/scraper error).
- **Rate limits**: `/auth/*` routes are limited to
  `AUTH_RATE_LIMIT_PER_MINUTE` (default 5/min) per client IP; all other routes
  documented here are limited to `RATE_LIMIT_PER_MINUTE` (default 60/min) per
  client IP. Limits are in-memory per app instance, not shared across
  replicas.
- **Permissions**: Enforced via `Role.permissions` (a string list on the
  user's role, e.g. `"*"` or `"vulnerabilities:read"`). Superusers
  (`is_superuser=True`) bypass permission checks.

---

## Health

### `GET /health`

Unversioned (not under `/api/v1`). No auth, no rate limit. Used by the
Docker/compose healthcheck.

**Response `200`**
```json
{"status": "ok"}
```

---

## Auth — `/api/v1/auth`

Rate limit: `AUTH_RATE_LIMIT_PER_MINUTE` (default 5/min).

### `POST /api/v1/auth/register`

Creates a new user **and a brand-new organization** — self-service
registration always creates an organization; it never joins an existing
one. `organization_name` is slugified and looked up first; if an
organization with that slug already exists, the request is rejected with
`409 AlreadyExistsError` ("... Ask an administrator of that organization to
create an account for you."). Otherwise a new `Organization` is created and
the new user becomes its first `admin` (`permissions: ["*"]`). Also rejects
duplicate emails with `409 AlreadyExistsError`. To add a user to an
*existing* organization, an admin of that organization must use
`POST /api/v1/users` instead (see below) — see `docs/security.md` for the
full registration/authorization model.

**Request body** (`UserRegister`)
```json
{
  "email": "user@example.com",
  "password": "min 8, max 128 chars",
  "full_name": "Jane Doe",
  "organization_name": "Acme Corp"
}
```

**Response `201`** (`UserRead`)
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "is_active": true,
  "is_superuser": false,
  "organization_id": "uuid",
  "role_id": "uuid",
  "created_at": "2026-07-10T00:00:00Z"
}
```

### `POST /api/v1/auth/login`

Verifies email/password, requires `is_active=True`, issues a fresh
access/refresh token pair.

**Request body** (`UserLogin`)
```json
{"email": "user@example.com", "password": "..."}
```

**Response `200`** (`TokenResponse`)
```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer"
}
```

Access tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30 min);
refresh tokens after `REFRESH_TOKEN_EXPIRE_DAYS` (default 7 days).

### `POST /api/v1/auth/refresh`

Decodes the refresh token (rejects access tokens presented here — checked via
the JWT's `type` claim), re-issues a new access/refresh pair.

**Request body** (`RefreshTokenRequest`)
```json
{"refresh_token": "<jwt>"}
```

**Response `200`**: same shape as `/auth/login`.

---

## Users — `/api/v1/users`

Rate limit: `RATE_LIMIT_PER_MINUTE` (default 60/min). Requires auth.

### `POST /api/v1/users`

Admin-created user. Requires the `users:manage` permission (or superuser).
The new user always has `is_superuser=False` and inherits
`organization_id` from the requesting admin's own organization. Validates
that `role_name` refers to an existing role and the email isn't already
taken.

**Request body** (`UserCreate`)
```json
{
  "email": "newuser@example.com",
  "password": "min 8, max 128 chars",
  "full_name": "New User",
  "role_name": "analyst"
}
```

**Response `201`** (`UserRead`) — same shape as in `/auth/register`.

---

## Organizations — `/api/v1/organizations`

Rate limit: `RATE_LIMIT_PER_MINUTE` (default 60/min). Requires auth.

### `GET /api/v1/organizations/me`

Returns the requesting user's own organization. No permission beyond a
valid token is required (there's no cross-tenant listing endpoint — a user
can only ever see their own organization).

**Response `200`** (`OrganizationRead`)
```json
{
  "id": "uuid",
  "name": "Acme Corp",
  "slug": "acme-corp",
  "created_at": "2026-07-10T00:00:00Z"
}
```

---

## Roles — `/api/v1/roles`

Rate limit: `RATE_LIMIT_PER_MINUTE` (default 60/min). Requires auth.
**Roles are global, not scoped per organization** — creating a role affects
every organization in the system (see `docs/security.md` for the
implication).

### `POST /api/v1/roles`

Requires the `roles:manage` permission (or superuser). Rejects a duplicate
`name` with `409 AlreadyExistsError`. `permissions` is a free-form list of
strings (there's no central registry validating these against what
endpoints actually check).

**Request body** (`RoleCreate`)
```json
{"name": "analyst", "permissions": ["vulnerabilities:read", "sources:read"]}
```

**Response `201`** (`RoleRead`)
```json
{
  "id": "uuid",
  "name": "analyst",
  "permissions": ["vulnerabilities:read", "sources:read"],
  "created_at": "2026-07-10T00:00:00Z"
}
```

### `GET /api/v1/roles`

Requires the `roles:read` permission (or superuser). Returns all roles,
ordered by name (no pagination — role counts are expected to stay small).

**Response `200`**: `list[RoleRead]`

### `GET /api/v1/roles/{role_id}`

Requires the `roles:read` permission (or superuser). Returns
`404 NotFoundError` if no role with that ID exists.

**Response `200`** (`RoleRead`)

---

## Sources — `/api/v1/sources`

Rate limit: `RATE_LIMIT_PER_MINUTE` (default 60/min). Requires auth. Sources
are populated automatically by the scraper ingestion jobs (see
`docs/architecture.md`) — there's no create/update route; this is a
read-only view of what's been ingested from.

### `GET /api/v1/sources`

Requires the `sources:read` permission (or superuser). Returns all sources,
ordered by name (no pagination — source counts are expected to stay small,
today: NVD, CISA-KEV, MITRE, RedHat).

**Response `200`**: `list[SourceRead]`
```json
[
  {
    "id": "uuid",
    "name": "NVD",
    "source_type": "api",
    "base_url": "https://services.nvd.nist.gov/rest/json/cves/2.0",
    "created_at": "2026-07-10T00:00:00Z"
  }
]
```

### `GET /api/v1/sources/{source_id}`

Requires the `sources:read` permission (or superuser). Returns
`404 NotFoundError` if no source with that ID exists.

**Response `200`** (`SourceRead`)

---

## Scrape jobs — `/api/v1/scrape-jobs`

Rate limit: `RATE_LIMIT_PER_MINUTE` (default 60/min). Requires auth and the
`scrape_jobs:read` permission (or superuser) on both routes. Read-only —
rows are created and updated only by the scheduled ingestion tasks
themselves (see `docs/architecture.md`), never via the API.

Each row represents one run of one of the four scheduled ingestion jobs
(`nvd_ingestion`, `cisa_kev_ingestion`, `redhat_ingestion`,
`mitre_backfill`) — a `running` row is inserted when the job starts, then
updated to `success` (with `items_processed`) or `failed` (with
`error_message`) when it finishes. This is what gives operational
visibility into whether scheduled ingestion is actually working — before
this existed, a failing scraper only showed up in application logs.

### `GET /api/v1/scrape-jobs`

Paginated, optionally filtered by `job_name`, newest first.

**Query parameters**

| Param | Type | Default | Notes |
|---|---|---|---|
| `page` | int | 1 | 1-indexed, `ge=1` |
| `page_size` | int | 20 | `ge=1, le=100` |
| `job_name` | string | — | exact match, e.g. `nvd_ingestion` |

**Response `200`** (`Page[ScrapeJobRead]`)
```json
{
  "items": [
    {
      "id": "uuid",
      "job_name": "nvd_ingestion",
      "status": "success",
      "started_at": "2026-07-10T06:00:00Z",
      "finished_at": "2026-07-10T06:00:42Z",
      "items_processed": 50,
      "error_message": null,
      "created_at": "2026-07-10T06:00:00Z"
    }
  ],
  "total": 12,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

`status` is one of `running`, `success`, `failed` (see
`app/models/scrape_job.py`). `error_message` is populated only when
`status` is `failed`, as a concise `"<ExceptionType>: <message>"` summary
(not a full traceback).

### `GET /api/v1/scrape-jobs/{scrape_job_id}`

Returns `404 NotFoundError` if no job with that ID exists.

**Response `200`** (`ScrapeJobRead`)

---

## Vulnerabilities — `/api/v1/vulnerabilities`

Rate limit: `RATE_LIMIT_PER_MINUTE` (default 60/min). Requires auth and the
`vulnerabilities:read` permission (or superuser) on both routes.

### `GET /api/v1/vulnerabilities`

Paginated, filtered, sortable list.

**Query parameters**

| Param | Type | Default | Notes |
|---|---|---|---|
| `page` | int | 1 | 1-indexed, `ge=1` |
| `page_size` | int | 20 | `ge=1, le=100` |
| `q` | string | — | keyword match across `cve_id`, `title`, `description` (ILIKE) |
| `severity` | string | — | exact match, e.g. `LOW`/`MEDIUM`/`HIGH`/`CRITICAL` |
| `is_known_exploited` | bool | — | filters to CISA KEV-flagged CVEs |
| `affected_vendor` | string | — | ILIKE match |
| `affected_product` | string | — | ILIKE match |
| `min_cvss` / `max_cvss` | float | — | `0`–`10`, inclusive range |
| `sort_by` | string | `published_date` | one of `cve_id`, `published_date`, `updated_date`, `cvss_score` (whitelisted — other values are rejected, not passed through to SQL) |
| `sort_order` | string | `desc` | `asc` or `desc` |

**Response `200`** (`Page[VulnerabilityRead]`)
```json
{
  "items": [ /* VulnerabilityRead objects, see below */ ],
  "total": 137,
  "page": 1,
  "page_size": 20,
  "total_pages": 7
}
```

### `GET /api/v1/vulnerabilities/{cve_id}`

Fetch a single vulnerability by its CVE ID (e.g. `CVE-2024-12345`). Returns
`404 NotFoundError` if no matching row exists.

**Response `200`** (`VulnerabilityRead`)
```json
{
  "id": "uuid",
  "cve_id": "CVE-2024-12345",
  "title": "...",
  "description": "...",
  "severity": "HIGH",
  "cvss_score": 8.1,
  "published_date": "2024-01-15T00:00:00Z",
  "updated_date": "2024-02-01T00:00:00Z",
  "references": ["https://..."],
  "affected_vendor": "Acme",
  "affected_product": "Widget",
  "is_known_exploited": true,
  "kev_date_added": "2024-01-20",
  "kev_due_date": "2024-02-10",
  "ransomware_campaign_use": "Known",
  "cve_state": "PUBLISHED",
  "assigner_org": "mitre.org",
  "date_reserved": "2024-01-01T00:00:00Z",
  "redhat_severity": "important",
  "redhat_statement": "...",
  "source_id": "uuid",
  "created_at": "2024-01-15T00:05:00Z"
}
```

Fields populated depend on which sources have enriched that CVE — KEV fields
are only set if CISA has flagged it, MITRE fields only if the MITRE backfill
job has processed it, and so on. Any unset field is `null`.

---

## Not yet available

The following are referenced by directory/file names in the codebase but have
no working routes yet: advisories, assets, and free-text/cross-entity
search. See `docs/architecture.md` for the full list of scaffolded-but-empty
modules.
