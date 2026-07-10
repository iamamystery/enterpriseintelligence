# ETIP Deployment

## Requirements

- Python 3.12+ (CI and Docker images currently pin `3.14`; see
  `.python-version` / `Dockerfile`)
- [`uv`](https://github.com/astral-sh/uv) for dependency management
- PostgreSQL 16 and MongoDB 7 (run via Docker Compose locally, or point at
  managed instances in production)

## Environment variables

Copy `.env.example` to `.env` and fill in real values. All settings are
defined in `app/core/config.py` (`Settings`, loaded via `pydantic-settings`).

| Variable | Default | Notes |
|---|---|---|
| `ENVIRONMENT` | `development` | free-form label |
| `DEBUG` | `false` | enables SQLAlchemy `echo` and Postgres/Mongo debug behavior |
| `POSTGRES_HOST` | `localhost` | |
| `POSTGRES_PORT` | `5432` | compose maps host `5433` → container `5432` |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | — | required, no default |
| `MONGODB_URL` | — | required, no default |
| `MONGODB_DB_NAME` | `etip_raw_intel` | |
| `JWT_SECRET_KEY` | — | required; must be a real secret in any non-local environment |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON list |
| `LOG_LEVEL` | `INFO` | |
| `RATE_LIMIT_PER_MINUTE` | `60` | general API rate limit |
| `AUTH_RATE_LIMIT_PER_MINUTE` | `5` | stricter limit on `/auth/*` |
| `NVD_API_KEY` | none | optional; raises NVD's rate limit if set |
| `SCRAPER_REQUEST_TIMEOUT` | `30` | seconds |
| `SCRAPER_USER_AGENT` | `ETIP-Bot/1.0` | sent on all outbound scraper requests |
| `SCRAPE_JOB_RETENTION_DAYS` | `90` | finished `scrape_jobs` rows older than this are deleted daily; see `docs/architecture.md` "Background jobs" |

`DATABASE_URL` (asyncpg) and `SYNC_DATABASE_URL` (psycopg2, used by Alembic)
are computed automatically from the `POSTGRES_*` fields — don't set them
directly.

**Secrets**: `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, and Mongo credentials
should never be committed. `.env` is gitignored; only `.env.example` (with
placeholder values) is tracked.

## Local development

```bash
uv sync                      # install dependencies (incl. dev group)
cp .env.example .env         # then edit with local values
docker compose up -d postgres mongodb   # start just the databases
uv run alembic upgrade head  # apply migrations
uv run python main.py        # runs uvicorn with --reload on :8000
```

`main.py` is a thin dev entrypoint (`uvicorn.run("app.main:app", reload=True)`)
distinct from the production Docker `CMD`, which runs uvicorn without reload.

Run tests: `uv run pytest -v` (pytest-asyncio is configured in
`pyproject.toml` with `asyncio_mode = "auto"`, session-scoped event loop).

## Docker Compose (full stack)

```bash
docker compose up -d --build
```

Three services are defined in `docker-compose.yml`:

- **`postgres`** (`postgres:16-alpine`) — host port `${POSTGRES_PORT:-5433}`
  → container `5432`, healthcheck via `pg_isready`, data persisted in the
  `postgres_data` named volume.
- **`mongodb`** (`mongo:7`, `mongod --auth`) — host port `27018` →
  container `27017`, root credentials from `MONGO_ROOT_USER` (default
  `etip`) / `MONGO_ROOT_PASSWORD`, healthcheck via `mongosh --eval
  db.adminCommand('ping')`, data in the `mongodb_data` volume.
- **`app`** — built from the local `Dockerfile`, reads `.env` via `env_file`
  but overrides `POSTGRES_HOST=postgres`, `POSTGRES_PORT=5432`, and
  `MONGODB_URL` to point at the compose service names instead of localhost.
  Startup command is `sh -c "alembic upgrade head && uvicorn app.main:app
  --host 0.0.0.0 --port 8000"` — **migrations run automatically on every
  container start**, before the API begins serving. Host port `8000` →
  container `8000`. `depends_on` both databases with
  `condition: service_healthy`, and has its own healthcheck against
  `GET /health`.

`docker/nginx/`, `docker/postgres/`, `docker/mongodb/`, and `docker/redis/`
directories exist as empty placeholders (no reverse-proxy config, DB init
scripts, or Redis service are wired up yet — Celery/Redis are unused, see
`docs/architecture.md`).

## Dockerfile

Multi-stage build:

1. **`builder`** (`python:3.14-slim`) — copies the `uv` binary from
   `ghcr.io/astral-sh/uv:latest`, runs `uv sync --locked --no-dev
   --no-install-project` against just `pyproject.toml`/`uv.lock` first (for
   Docker layer caching), then copies the full source and runs
   `uv sync --locked --no-dev` again to install the project itself.
2. **`runtime`** (`python:3.14-slim`) — creates a non-root system user/group
   (`app`), copies the built app + `.venv` from the builder stage with
   `--chown=app:app`, sets `PATH` to prefer the venv, runs as `USER app`
   (never root), exposes `8000`, and defines a container-level
   `HEALTHCHECK` hitting `/health`. Default `CMD` runs uvicorn directly
   without the `alembic upgrade head` step — the compose file overrides
   `CMD` to run migrations first; if you run this image outside compose
   (e.g. in a different orchestrator), you're responsible for running
   migrations separately before or via an init container.

## Migrations

Alembic, sync driver (`SYNC_DATABASE_URL`, psycopg2). Common commands:

```bash
uv run alembic upgrade head           # apply all pending migrations
uv run alembic revision --autogenerate -m "message"   # generate a new migration
uv run alembic downgrade -1           # roll back one migration
```

Five migrations exist today (see `docs/database.md` for the full chain and
what each one adds). `alembic/env.py` imports `app.models` so autogenerate
can see the full `Base.metadata`.

## CI

`.github/workflows/ci.yml` runs on push/PR to `main`:

- Spins up a `postgres:16-alpine` service container (no Mongo service — the
  test suite doesn't appear to need a live Mongo instance for what's
  currently covered)
- Installs deps via `astral-sh/setup-uv` + `uv sync --locked`
- Runs `uv run pytest -v`

CI uses its own hardcoded env values (test JWT secret, `etip`/`changeme`
Postgres creds) distinct from `.env`/`.env.example` — these are CI-only and
not meant to be reused anywhere real.

## Health checks

`GET /health` (unversioned, defined directly in `app/main.py`) returns
`{"status": "ok"}` and is used by both the Docker Compose `app` healthcheck
and the Dockerfile's own `HEALTHCHECK` directive. It does not currently
check downstream Postgres/Mongo connectivity — it's a liveness check, not a
full readiness check.

## Scheduled jobs in production

APScheduler runs in-process inside the `app` service (started/stopped via
the FastAPI `lifespan` hook) — there is no separate worker container or
process. This means:

- Scaling the `app` service to multiple replicas will run the same
  scheduled ingestion jobs multiple times in parallel (no leader election or
  distributed locking exists today).
- Rate limiting is also in-memory per instance, so multiple replicas each
  get their own independent rate-limit budget rather than a shared one.

Both are worth addressing (e.g. via a shared lock/broker, or moving jobs to
a single dedicated instance) before running more than one `app` replica.
