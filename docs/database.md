# ETIP Database

ETIP uses two databases for two different purposes: **PostgreSQL** as the
system of record for structured, queryable entities, and **MongoDB** as an
append-only raw-payload lake for scraper output.

## PostgreSQL

### Connection setup

Two engines are configured from the same credentials
(`app/core/config.py`: `POSTGRES_HOST/PORT/USER/PASSWORD/DB`), because
SQLAlchemy async requires a different driver than Alembic's sync migration
runner:

- **Async** (`app/database/postgres.py`) — `settings.DATABASE_URL` (asyncpg
  driver). `create_async_engine(..., pool_pre_ping=True)` +
  `async_sessionmaker(expire_on_commit=False)`. `get_db()` is an async
  generator (`AsyncSession` per request) used as the `DBSession` FastAPI
  dependency everywhere in the API.
- **Sync** (`app/database/sync_session.py`) — `settings.SYNC_DATABASE_URL`
  (psycopg2 driver). Same shape (`create_engine` + `sessionmaker` +
  `get_sync_db()` generator), used by Alembic (`alembic/env.py` falls back to
  `settings.SYNC_DATABASE_URL` when no `sqlalchemy.url` is set in
  `alembic.ini`).

Both URLs are computed properties on `Settings` built from the same
Postgres fields, so there's a single source of truth for credentials.

### Base model and mixins (`app/database/base.py`)

```python
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

A custom naming convention (`ix_...`, `uq_<table>_<column>`,
`ck_<table>_<constraint>`, `fk_<table>_<column>_<referred_table>`,
`pk_<table>`) is applied so every index/constraint/foreign key gets a
deterministic, consistent name across Alembic-generated migrations — this
matters for autogenerate diffing and for being able to `DROP CONSTRAINT` by
name in hand-written migrations.

Every model composes two mixins:

- `UUIDMixin` — `id: UUID` primary key (Postgres native `uuid` type),
  defaulted client-side via `uuid.uuid4`.
- `TimestampMixin` — `created_at` / `updated_at`, both timezone-aware
  `DateTime`, set via `server_default=func.now()` (`updated_at` also has
  `onupdate=func.now()`, refreshed by Postgres on every `UPDATE`).

### Schema

Five tables exist today (`app/models/__init__.py` registers exactly these
five with SQLAlchemy's mapper):

**`organizations`**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| created_at / updated_at | timestamptz | |
| name | varchar(255) | |
| slug | varchar(255) | unique, indexed |

**`roles`**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| created_at / updated_at | timestamptz | |
| name | varchar(100) | unique |
| permissions | text[] | default `[]`; e.g. `"*"`, `"vulnerabilities:read"`, `"users:manage"` |

**`users`**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| created_at / updated_at | timestamptz | |
| email | varchar | unique, indexed |
| hashed_password | varchar | bcrypt hash |
| full_name | varchar | |
| is_active | bool | default `true` |
| is_superuser | bool | default `false` |
| organization_id | UUID FK → organizations.id | |
| role_id | UUID FK → roles.id | |

**`sources`**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| created_at / updated_at | timestamptz | |
| name | varchar | unique, e.g. `NVD`, `CISA-KEV`, `MITRE`, `RedHat` |
| source_type | varchar(20) | e.g. `api` |
| base_url | varchar | |

**`vulnerabilities`**

A single wide table that accumulates enrichment columns from every scraper
source, rather than one table per source:

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| created_at / updated_at | timestamptz | |
| cve_id | varchar(30) | unique, indexed |
| title | varchar(500) | |
| description | text | |
| severity | varchar(20) nullable | |
| cvss_score | float nullable | |
| published_date / updated_date | timestamptz nullable | |
| references | text[] | default `[]` |
| affected_vendor / affected_product | varchar(255) nullable | |
| **CISA KEV**: is_known_exploited | bool | default `false` |
| kev_date_added / kev_due_date | date nullable | |
| ransomware_campaign_use | varchar(50) nullable | |
| **MITRE**: cve_state | varchar(20) nullable | |
| assigner_org | varchar(255) nullable | |
| date_reserved | timestamptz nullable | |
| **Red Hat**: redhat_severity | varchar(20) nullable | |
| redhat_statement | text nullable | |
| source_id | UUID FK → sources.id | |

**`scrape_jobs`**

One row per run of a scheduled ingestion job (see `docs/architecture.md`
"Background jobs"):

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| created_at / updated_at | timestamptz | |
| job_name | varchar(100) | indexed; e.g. `nvd_ingestion`, `mitre_backfill` |
| status | varchar(20) | `running`, `success`, or `failed` |
| started_at | timestamptz | |
| finished_at | timestamptz nullable | set when the run completes |
| items_processed | integer nullable | set on success |
| error_message | text nullable | set on failure, `"<ExceptionType>: <message>"` |

**`advisories`**

A vendor/authority security bulletin — distinct from `vulnerabilities`,
which is one row per enriched CVE. Resource-layer only today: rows are
created via `POST /api/v1/advisories`, not by any scraper yet.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| created_at / updated_at | timestamptz | |
| advisory_id | varchar(50) | unique, indexed; e.g. `ICSA-24-123-01`, `RHSA-2024:1234` |
| title | varchar(500) | |
| summary | text | |
| url | varchar(1024) nullable | |
| published_date | timestamptz nullable | |
| cve_ids | text[] | default `[]`; plain strings, not validated against `vulnerabilities` |
| source_id | UUID FK → sources.id | |

**`assets`**

The first tenant-scoped table — every other table so far is either global
reference data or reached via a single-row "my own" lookup. Resource-layer
only: rows exist only via `POST /api/v1/assets`, no scraper populates this.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| created_at / updated_at | timestamptz | |
| name | varchar(255) | |
| asset_type | varchar(50) | free string, e.g. `server`, `workstation`, `application` |
| vendor | varchar(255) nullable | mirrors `Vulnerability.affected_vendor` naming |
| product | varchar(255) nullable | mirrors `Vulnerability.affected_product` naming |
| version | varchar(100) nullable | |
| ip_address | varchar(45) nullable | sized for IPv6 |
| is_active | bool | default `true` |
| organization_id | UUID FK → organizations.id | indexed |

### Relationships

```
Organization 1---N User
Organization 1---N Asset
Role         1---N User
Source       1---N Vulnerability
Source       1---N Advisory
```

`Organization` and `Role` are both referenced from `User`
(`organization_id`, `role_id`); `Vulnerability` and `Advisory` both
reference `Source` (`source_id`); `Asset` references `Organization`
(`organization_id`) — this is the FK that makes tenant-scoped queries
possible (`WHERE organization_id = :caller_org_id`). `scrape_jobs` has no
foreign keys — it's identified only by `job_name`, a free-form string
matching the APScheduler job IDs in `app/tasks/scheduler.py`, not a FK to
a job-definitions table. `Advisory.cve_ids` is a plain string array, not a
foreign key or join table — there is no enforced many-to-many between
advisories and vulnerabilities (an advisory can reference a `cve_id` that
doesn't exist, or doesn't exist yet, in `vulnerabilities`). Likewise,
`Asset` and `Vulnerability` have no FK or join table between them at
all — the asset-to-vulnerability matching feature (`docs/architecture.md`)
is computed at query time by comparing `vendor`/`product` string columns
on both tables, not by a stored relationship.

One model file exists but defines no table and isn't imported anywhere
(not part of any migration): `app/models/audit_log.py`. Treat it as a
placeholder for future schema, not dead code.

### Migrations (Alembic)

`alembic/env.py` imports `app.models` (to populate `Base.metadata` for
autogenerate) and falls back to `settings.SYNC_DATABASE_URL` when
`alembic.ini` has no `sqlalchemy.url` configured. Eight migrations exist
today, forming one linear chain (no branches):

1. `365455051ed7` — create `organizations`, `roles`, `users`
2. `39d8703ff0b5` — create `sources`, `vulnerabilities`
3. `90a34578c5c1` — add CISA KEV enrichment columns to `vulnerabilities`
4. `684afb0c8c71` — add MITRE metadata columns to `vulnerabilities`
5. `837408e55466` — add Red Hat enrichment columns to `vulnerabilities`
6. `905078e87c24` — create `scrape_jobs`
7. `9d684da259bc` — create `advisories`
8. `a2ed45956a10` — create `assets`

Migrations 1–5 mirror the "enrich in place" design: each new scraper
integration ships as a migration adding columns to `vulnerabilities` rather
than a new joined table. Migrations 6–8 are genuinely new tables.

**Running migrations**: `alembic upgrade head` (run automatically on
container start in `docker-compose.yml`, before `uvicorn` starts).

### Repository layer

`app/repositories/postgres/` wraps each table in a thin repository class
(constructor takes an `AsyncSession`, methods are `select()` + `execute()`
wrappers — no shared base repository class):

- `OrganizationRepository` — `get_by_id`, `get_by_slug`, `create`
- `RoleRepository` — `get_by_id`, `get_by_name`, `list_all`, `create`
- `SourceRepository` — `get_by_id`, `get_by_name`, `list_all`, `create`
- `UserRepository` — `get_by_id` (eager-loads `.role` via `selectinload`),
  `get_by_email`, `create`
- `VulnerabilityRepository` — the most complex one:
  - `get_by_cve_id(cve_id)`
  - `search(keyword, severity, is_known_exploited, affected_vendor,
    affected_product, min_cvss, max_cvss, sort_by, sort_order, limit,
    offset) -> (items, total_count)` — builds filters dynamically (ILIKE for
    keyword/vendor/product, exact match for severity, range for CVSS) and
    validates `sort_by` against a `SORTABLE_COLUMNS` whitelist to prevent
    arbitrary-column SQL injection via the sort parameter
  - `list_cve_ids_missing_mitre_enrichment(limit=25)` — finds rows with
    `cve_state IS NULL`, used to drive the MITRE backfill job
  - `create` / `upsert` (upsert looks up by `cve_id`, overwrites mutable
    enrichment fields on the existing row or inserts a new one)
- `ScrapeJobRepository` — `create`, `get_by_id`,
  `list_recent(job_name=None, limit, offset) -> (items, total_count)`
  (ordered `started_at` descending)
- `AdvisoryRepository` — `create`, `get_by_id` (internal UUID),
  `get_by_advisory_id` (external string ID, used by the API detail route),
  `list_recent(source_id=None, limit, offset) -> (items, total_count)`
  (ordered `published_date` descending, nulls last)
- `AssetRepository` — `create`, `get_by_id`,
  `list_for_organization(organization_id, limit, offset) -> (items, total_count)`
  (ordered by `name`; `organization_id` is a required, not optional,
  filter — there's no method that lists across organizations)

`audit_repository.py` exists but is empty — no code, since `AuditLog`'s
backing table doesn't exist yet.

## MongoDB

### Connection setup (`app/database/mongodb.py`)

A single module-level Motor client and database handle, created at import
time (not a per-request FastAPI dependency):

```python
client = AsyncIOMotorClient(settings.MONGODB_URL)
database = client[settings.MONGODB_DB_NAME]  # default db name: "etip_raw_intel"

def get_mongodb() -> AsyncIOMotorDatabase:
    return database
```

### Schema

No formal schema (Mongo is schemaless) — one collection is used today:

**`raw_intel`** — append-only ingestion log, one document per scraper call:

```json
{
  "_id": "ObjectId",
  "source": "NVD | CISA-KEV | MITRE | RedHat",
  "payload": { /* exact upstream JSON, unmodified */ },
  "fetched_at": "ISODate (UTC)"
}
```

`RawIntelRepository.insert_raw(source, payload)` (in
`app/repositories/mongo/raw_intel_repository.py`) is the only method — it
inserts and returns the new document's `_id` as a string. There is
currently no read/query path back out of `raw_intel` from the application;
it exists purely as an audit/replay trail of exactly what each source
returned, decoupled from the normalized Postgres `vulnerabilities` table
that the API actually serves reads from.

### Why two databases

Every ingestion (`ScrapingService`, see `docs/architecture.md`) writes the
raw source payload to Mongo *before* mapping and upserting the normalized
result into Postgres. This means the original upstream data is never lost
to a mapping bug or schema change — the Postgres schema can evolve (as it
has, one migration per source) without needing to re-fetch from the
upstream APIs, since the raw JSON is retained in Mongo.

## Local database access

`docker-compose.yml` exposes both databases on non-default host ports to
avoid clashing with any locally-installed Postgres/Mongo:

- Postgres: host `${POSTGRES_PORT:-5433}` → container `5432`
- MongoDB: host `27018` → container `27017` (auth enabled, `mongod --auth`)

See `docs/deployment.md` for the full environment variable list and compose
setup.
