# ETIP Architecture

ETIP (Enterprise Threat Intelligence Platform) is a FastAPI backend that ingests
vulnerability intelligence from public sources (NVD, CISA KEV, MITRE, Red Hat),
normalizes it into a Postgres schema, and exposes it through a versioned REST API
protected by JWT auth and role-based permissions.

This document describes the codebase as it stands today. Several modules are
scaffolded (empty files with the intended name and location) but not yet
implemented — these are called out explicitly so the doc doesn't overstate what
exists.

## Stack

- **API**: FastAPI + Uvicorn, ASGI, versioned under `/api/v1`
- **Relational store**: PostgreSQL 16, SQLAlchemy 2.0 async ORM (`asyncpg` driver
  at runtime, `psycopg2` for Alembic's sync migrations)
- **Document store**: MongoDB 7 via Motor, used as an append-only raw-payload lake
- **Auth**: PyJWT (HS256) + bcrypt
- **Scheduling**: APScheduler (`AsyncIOScheduler`), running in-process
- **Migrations**: Alembic
- **Packaging**: `uv` (`pyproject.toml` / `uv.lock`), Python 3.12+
- **Tests**: pytest + pytest-asyncio
- **Deployment**: multi-stage Dockerfile + docker-compose (Postgres, MongoDB, app)

## Request lifecycle

```
client
  -> CORSMiddleware (app/main.py)
  -> APIRouter (app/api/v1/router.py)
      -> per-router rate-limit dependency (auth_rate_limit / rate_limit)
      -> auth dependency (get_current_user, decodes JWT)
      -> permission dependency (require_permission("resource:action"))
      -> endpoint function
          -> service (business logic)
              -> repository (SQLAlchemy query/mutation)
                  -> Postgres
  -> ETIPError / HTTPException -> JSON error response
```

`app/main.py` builds the `FastAPI` app, registers `CORSMiddleware`, calls
`register_exception_handlers`, mounts `api_router` under `settings.API_V1_PREFIX`,
and defines `GET /health` directly (this route is unversioned and lives outside
the `/api/v1` router). A `lifespan` context manager starts/stops the APScheduler
instance alongside the app process.

There is currently **no custom middleware** beyond CORS — `app/core/middleware/`
(request ID, request logging, error-handling middleware) exists as empty stub
files. Rate limiting is implemented as a FastAPI dependency, not middleware (see
below), and request/response logging is limited to whatever `logging.dictConfig`
setup is in `app/core/logging.py`.

## Layering

The app follows a fairly conventional layered structure:

```
app/api/          - FastAPI routers + endpoint functions (HTTP concerns only)
app/api/dependencies/ - reusable Depends() providers: db session, auth, permissions,
                        rate limiting, pagination
app/schemas/       - Pydantic request/response models
app/services/      - business logic, orchestrates repositories
app/repositories/  - data access (Postgres via SQLAlchemy, Mongo via Motor)
app/models/        - SQLAlchemy ORM models
app/scrapers/      - per-source HTTP clients + JSON-to-model mappers
app/tasks/         - APScheduler job definitions that call services
app/core/          - config, security, exceptions, logging
app/database/      - engine/session setup for Postgres (async + sync) and Mongo
```

Endpoints depend only on services; services depend only on repositories;
repositories are the only layer that talks to SQLAlchemy/Motor directly. Routers
never construct SQL themselves.

## Configuration

`app/core/config.py` defines a single `pydantic-settings` `Settings` class loaded
from `.env`, cached via `@lru_cache` and exposed as the `settings` singleton. It
holds: app metadata, Postgres connection fields (plus computed `DATABASE_URL` /
`SYNC_DATABASE_URL` properties for the async and sync drivers respectively),
Mongo URL/db name, JWT secret/algorithm/token lifetimes, CORS origins, log level,
rate-limit thresholds (general and auth-specific), and scraper settings
(`NVD_API_KEY`, request timeout, user agent).

## Dual-database design

Postgres is the system of record for structured, queryable entities
(`Organization`, `Role`, `User`, `Source`, `Vulnerability`). MongoDB is used
purely as a write-only raw-intel lake: every scraper run writes the exact
upstream JSON payload (`{source, payload, fetched_at}`) into a `raw_intel`
collection via `RawIntelRepository.insert_raw`, before the same data is
mapped and upserted into the Postgres `vulnerabilities` table. This preserves
the original source data for audit/replay purposes, decoupled from the
normalized schema, which is free to evolve without losing history.

See `docs/database.md` for schema and connection details.

## Auth and permissions

JWT-based, stateless, dual-token (access + refresh), HS256-signed with a shared
secret (`app/core/security.py`). `get_current_user` (`app/api/dependencies/auth.py`)
decodes the bearer token, rejects refresh tokens presented as access tokens, and
loads the active `User`. Authorization is a simple string-based permission-list
model: `Role.permissions` is a Postgres string array (e.g. `"*"`,
`"vulnerabilities:read"`, `"users:manage"`); `require_permission(...)`
(`app/api/dependencies/permissions.py`) is a dependency factory that checks the
current user's role for the wildcard or the exact permission string, or allows
`is_superuser` users unconditionally. There is no separate permissions table —
permissions live directly on `Role`.

See `docs/security.md` for full detail, including a note on the registration
flow's organization-joining behavior.

## Rate limiting

`app/api/dependencies/rate_limit.py` implements an in-memory sliding-window
limiter (`InMemoryRateLimiter`, keyed by `time.monotonic()` timestamps per
client IP). Two singleton limiters exist: a general one
(`settings.RATE_LIMIT_PER_MINUTE`, default 60/min) and a stricter one for auth
routes (`settings.AUTH_RATE_LIMIT_PER_MINUTE`, default 5/min). They're applied
as router-level dependencies (`dependencies=[Depends(rate_limit)]` /
`dependencies=[Depends(auth_rate_limit)]`), not as ASGI middleware. Because
state is held in process memory, this limiter is per-instance only — it does
not coordinate across multiple app replicas.

## Error handling

`app/core/exceptions.py` defines a small domain exception hierarchy rooted at
`ETIPError(message, status_code)`, with subclasses `NotFoundError` (404),
`AlreadyExistsError` (409), `AuthenticationError` (401), `AuthorizationError`
(403), `ValidationError` (422), and `ScraperError` (502). A single handler
registered in `app/core/exception_handlers.py` converts any `ETIPError` into
`{"detail": message}` with the matching status code. Code that raises
FastAPI's own `HTTPException` directly (the auth and rate-limit dependencies do
this) is handled by FastAPI's default handler instead, which happens to produce
a compatible `{"detail": ...}` shape — so there are two parallel but
compatible error paths in play.

## Scraping and ingestion pipeline

There is no generic "base scraper" framework today, despite the directory
layout (`app/scrapers/base/base_scraper.py`, `cleaner.py`, `deduplicator.py`,
`normalizer.py`, `parser.py`) suggesting one — those files are empty stubs.
The only shared piece is `BaseAPIClient` (`app/scrapers/base/base_client.py`),
a thin `httpx.AsyncClient` wrapper providing a single `get(path, params)` used
by every source-specific client.

Each source is a self-contained module with a client and a mapper:

- **NVD** (`app/scrapers/nvd/`) — `NVDClient.fetch_recent_cves`; mapper parses
  CVSS v3.1/v3.0/v2 metrics, description, vendor/product (from the `affected`
  array or CPE `criteria` fallback).
- **CISA KEV** (`app/scrapers/cisa/`) — `CISAKEVClient.fetch_catalog`; mapper
  sets `is_known_exploited`, `kev_date_added`, `kev_due_date`,
  `ransomware_campaign_use`. (`advisory_feed.py` in this package is an empty,
  unimplemented stub — it would be the natural place to add a scraper for
  CISA's general advisory feed, which could then call
  `POST /api/v1/advisories` / `AdvisoryService.create_advisory` to
  auto-populate the `advisories` table the same way the other four scrapers
  populate `vulnerabilities` today.)
- **MITRE** (`app/scrapers/mitre/`) — `MITREClient.fetch_cve`; mapper parses
  the CVE 5.x JSON schema (`containers.cna`/`containers.adp`) for CVSS and
  MITRE-specific metadata (`cve_state`, `assigner_org`, `date_reserved`).
- **Red Hat** (`app/scrapers/vendor_advisories/redhat/`) — `RedHatClient`
  hits Red Hat's JSON security-data API (not HTML scraping, despite
  `beautifulsoup4`/`lxml` being dependencies and an empty `selectors.py`
  stub suggesting an HTML-based approach was originally planned).

`ScrapingService` (`app/services/scraping_service.py`) is the single
orchestrator tying all four sources together: for each source it gets-or-creates
the `Source` row, calls the client, writes the raw JSON to Mongo, maps the
payload to a `Vulnerability`, and upserts it into Postgres by `cve_id`.

## Background jobs

APScheduler (`app/tasks/scheduler.py`) runs in-process, started/stopped from the
FastAPI `lifespan` hook — there is no separate worker process. Four recurring
jobs are registered, each wrapping a `ScrapingService` call and swallowing
exceptions so one failing job doesn't crash the scheduler
(`app/tasks/scrape_tasks.py`):

| Job | Interval | Calls |
|---|---|---|
| `nvd_ingestion` | 6h | `ingest_nvd_recent` |
| `cisa_kev_ingestion` | 2h | `ingest_cisa_kev` |
| `redhat_ingestion` | 6h | `ingest_redhat_recent` |
| `mitre_backfill` | 12h | `ingest_mitre_cves` for CVEs missing MITRE enrichment |
| `scrape_job_cleanup` | 24h | `run_scrape_job_cleanup` (`app/tasks/cleanup_tasks.py`), see below |

Each ingestion run is tracked in the `scrape_jobs` table via a shared
`_run_tracked` helper: it inserts a `ScrapeJob` row with `status="running"`
before calling the ingestion function, then updates it to `"success"`
(with `items_processed`) or `"failed"` (with a concise `error_message`) in
a separate DB session — separate so the tracking write survives even if
the ingestion's own session/transaction is the thing that failed. This is
what `GET /api/v1/scrape-jobs` (see `docs/api.md`) exposes; before this
existed, a failing scraper was only visible in application logs, not
queryable via the API.

**Cleanup**: `run_scrape_job_cleanup` (`app/tasks/cleanup_tasks.py`) runs
once every 24 hours and deletes `scrape_jobs` rows where
`finished_at < now() - SCRAPE_JOB_RETENTION_DAYS days` (default 90,
configurable via the `SCRAPE_JOB_RETENTION_DAYS` env var). It deliberately
only ever deletes **finished** rows (`status IN (success, failed)`) — a
`status="running"` row that's older than the retention window is never
touched, because that almost certainly means the process that owned it
died mid-run without reaching `mark_success`/`mark_failed`, and a stuck
`running` row is a useful signal that something went wrong, not noise to
silently prune. Like the ingestion tasks, failures are caught and logged,
not raised, so a broken cleanup run doesn't crash the scheduler. This is
the only cleanup job implemented today — MongoDB's `raw_intel` collection
(see below) still grows unbounded with no retention policy, since raw
ingestion payloads are treated as an audit/replay log meant to be kept
rather than pruned.

Celery is scaffolded but unused: `app/tasks/celery_app.py` is empty, and no
broker (Redis) is wired into `docker-compose.yml` or the dependency list — the
`docker/redis/` directory exists but is empty.

## API surface

`app/api/v1/router.py` wires up every endpoint module now — `auth`,
`users`, `organizations`, `roles`, `sources`, `scrape_jobs`, `advisories`,
`assets`, `search`, and `vulnerabilities`:

- `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`
- `POST /api/v1/users` (admin-only, requires `users:manage`)
- `GET /api/v1/organizations/me` (any authenticated user, own org only)
- `POST /api/v1/roles`, `GET /api/v1/roles`, `GET /api/v1/roles/{role_id}`
  (require `roles:manage`/`roles:read`)
- `GET /api/v1/sources`, `GET /api/v1/sources/{source_id}` (require `sources:read`)
- `GET /api/v1/scrape-jobs`, `GET /api/v1/scrape-jobs/{scrape_job_id}`
  (require `scrape_jobs:read`)
- `POST /api/v1/advisories`, `GET /api/v1/advisories`,
  `GET /api/v1/advisories/{advisory_id}` (require `advisories:manage`/`advisories:read`)
- `POST /api/v1/assets`, `GET /api/v1/assets`, `GET /api/v1/assets/{asset_id}`
  (require `assets:manage`/`assets:read`, tenant-scoped to the caller's own organization)
- `GET /api/v1/assets/{asset_id}/vulnerabilities` (requires `vulnerabilities:read`)
  and `GET /api/v1/vulnerabilities/{cve_id}/assets` (requires `assets:read`) — the
  asset-to-vulnerability matching endpoints, see below
- `GET /api/v1/search` (requires `search:read`) — cross-entity keyword
  search over vulnerabilities, advisories, and assets, see below
- `GET /api/v1/vulnerabilities`, `GET /api/v1/vulnerabilities/{cve_id}`
  (require `vulnerabilities:read`)
- `GET /health` (unversioned, defined directly in `app/main.py`)

Every `app/api/v1/endpoints/*.py` file is now mounted — there is no more
scaffolded-but-empty endpoint module. See `docs/api.md` for the full route
reference.

Unlike `sources`/`scrape_jobs`, nothing populates `advisories`
automatically yet — it's a resource layer only (create/list/get), with
rows appearing only via `POST /api/v1/advisories`. The CISA advisory feed
(`app/scrapers/cisa/advisory_feed.py`, still empty) would be the natural
scraper to eventually auto-populate it, mirroring how `ScrapingService`
populates `vulnerabilities`.

`Asset` is the first genuinely tenant-scoped resource in the API —
`Organization`, `Role`, `Source`, `Vulnerability`, `Advisory`, and
`ScrapeJob` are all either global reference data or single "my own"
lookups (`organizations/me`). Every asset route filters by the requesting
user's `organization_id`, and `GET /api/v1/assets/{asset_id}` returns
`404` (not `403`) for an asset belonging to another organization, so the
error response can't be used to enumerate other tenants' asset IDs.

Note that `Role` is a global table with no `organization_id` — creating a
role via `POST /api/v1/roles` affects every organization in the system, not
just the caller's own. See `docs/security.md` for the implication of this.

## Asset-to-vulnerability matching

`AssetService.list_matching_vulnerabilities` and
`VulnerabilityService.list_matching_assets` are inverses of the same
underlying query, computed on the fly (nothing is precomputed or cached):
`VulnerabilityRepository.list_matching_vendor_product` and
`AssetRepository.list_matching_vendor_product` both filter on
`func.lower(vendor) == vendor.lower() AND func.lower(product) ==
product.lower()` — exact, case-insensitive equality on both fields, not a
substring/fuzzy match. If either side is missing `vendor` or `product`,
the service short-circuits to an empty result without querying.

This is a deliberately naive first pass, not real CPE/vendor-alias
matching: real-world vendor/product strings from different sources are
inconsistent (e.g. NVD might record `"Apache Software Foundation"` /
`"Log4j2"` while an asset entry says `"Apache"` / `"log4j"`), and nothing
here normalizes or aliases across those variants. It also never looks at
`Asset.version` — `Vulnerability` has no structured affected-version-range
field to compare against, only the free-text `affected_vendor`/
`affected_product`. In practice this means false negatives (a real match
missed due to naming differences) are more likely than false positives.
Improving this would mean either normalizing vendor/product strings at
ingestion time or introducing a CPE-based matching scheme — out of scope
for the current implementation.

## Cross-entity search

`SearchService.search` (`app/services/search_service.py`) fans a single
keyword query out to three repositories in parallel-in-spirit (sequential
`await`s, not concurrent) — `VulnerabilityRepository.search`,
`AdvisoryRepository.search`, `AssetRepository.search` — each doing its own
ILIKE substring match over that entity's text columns
(`cve_id`/`title`/`description` for vulnerabilities,
`advisory_id`/`title`/`summary` for advisories, `name`/`vendor`/`product`
for assets). Asset results are always filtered to the requesting user's
`organization_id`, regardless of anything else — tenant isolation isn't
optional here.

This is deliberately *not* a unified/paginated result set: each entity
type is capped at a fixed `limit` (default 10, max 50) with its own
`total` count, returned as three separate groups rather than one
interleaved, ranked list. There's no cross-type relevance ranking — a
`total: 47` vulnerability match and a `total: 1` advisory match are simply
two separate numbers, not merged or sorted against each other. This
matches the intended use case (a quick "does anything mention this"
lookup) rather than being a full search engine; anyone wanting to browse
all matches of one type should use that resource's own paginated list
endpoint instead.

`search:read` is a permission distinct from `vulnerabilities:read`,
`advisories:read`, and `assets:read` — a user granted only `search:read`
can see matches from all three types via this endpoint even without those
other permissions. This is an intentional simplification (single gate,
matching the one-permission-per-endpoint convention used everywhere else
in this codebase) rather than per-type permission filtering within a
single response, which would add real complexity for a coarse-grained
convenience endpoint. See `docs/security.md` for the implication.

## Data model

Eight models are registered with SQLAlchemy today (`app/models/__init__.py`):
`Organization`, `Role`, `User`, `Source`, `Vulnerability`, `ScrapeJob`,
`Advisory`, `Asset`. All use a shared `UUIDMixin` (UUID primary key) and
`TimestampMixin` (`created_at`/`updated_at`) from `app/database/base.py`.
`Vulnerability` is deliberately a single wide table that accumulates
enrichment columns from each source (KEV fields, MITRE metadata, Red Hat
severity) rather than per-source tables — the Alembic migrations mirror
this, one per source integration. `ScrapeJob` records one run of one
scheduled ingestion job (`job_name`, `status`, `started_at`/`finished_at`,
`items_processed`, `error_message`) — see "Background jobs" above.
`Advisory` represents a vendor/authority security bulletin (`advisory_id`,
`title`, `summary`, `url`, `published_date`, a plain `cve_ids: list[str]`
rather than a join table, and a `source_id` FK) — distinct from
`Vulnerability`, which is a single enriched CVE record; one advisory can
span multiple CVEs. `Asset` represents a piece of tracked IT infrastructure
(`name`, `asset_type`, `vendor`/`product`/`version`, `ip_address`,
`is_active`) belonging to exactly one `Organization` — `vendor`/`product`
mirror `Vulnerability.affected_vendor`/`affected_product` naming, and are
what the asset-to-vulnerability matching endpoints (above) query against.
`AuditLog` model file exists but is empty; no table for it exists in the
migration history. Full schema in `docs/database.md`.

## What's implemented vs. scaffolded

**Working today**: config, JWT auth (register/login/refresh), permission-based
authorization, in-memory rate limiting, CORS, dual Postgres+Mongo wiring, the
four scraper integrations orchestrated by `ScrapingService`, four scheduled
ingestion jobs with tracked run history, a scheduled `scrape_jobs` cleanup
job (retention-based, finished rows only, see above), vulnerability
list/search/get endpoints, organization/role/source/scrape-job/advisory/
asset endpoints (create + read, except organizations which is read-only),
asset-to-vulnerability matching (exact case-insensitive vendor/product
equality, see above), cross-entity keyword search over vulnerabilities/
advisories/assets (see above), eight Alembic migrations, Docker Compose
deployment. Every API endpoint module is now wired in — nothing left in
`app/api/v1/endpoints/` is an empty stub.

**Scaffolded, not yet implemented** (empty files present, no logic): custom
middleware (request ID, request logging, error handling), the `audit`
repository, the generic scraper base pipeline (cleaner, deduplicator,
normalizer, parser, base_scraper), a CISA advisory-feed scraper to
auto-populate `advisories` (currently create-only via the API), Celery
integration, a retention/cleanup policy for MongoDB's `raw_intel`
collection (which still grows unbounded — only `scrape_jobs` has cleanup
today), the `AuditLog` model, and several utility modules (`filters.py`,
`retry.py`, `utils/search.py` — note this is distinct from the
now-implemented `services/search_service.py`, `timezone.py`,
`validators.py`).

When extending ETIP, treat an existing-but-empty file as an intentional
placeholder for where that logic belongs, not as dead code to remove.
