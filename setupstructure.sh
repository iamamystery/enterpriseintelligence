#!/bin/bash

mkdir -p app/api/v1/endpoints
mkdir -p app/api/dependencies
mkdir -p app/core/middleware
mkdir -p app/database
mkdir -p app/models
mkdir -p app/schemas
mkdir -p app/repositories/postgres
mkdir -p app/repositories/mongo
mkdir -p app/services
mkdir -p app/scrapers/base
mkdir -p app/scrapers/nvd
mkdir -p app/scrapers/cisa
mkdir -p app/scrapers/mitre
mkdir -p app/scrapers/vendor_advisories/redhat
mkdir -p app/tasks
mkdir -p app/utils
mkdir -p alembic
mkdir -p tests/api
mkdir -p tests/services
mkdir -p tests/repositories
mkdir -p tests/scrapers
mkdir -p tests/models
mkdir -p docs
mkdir -p docker/postgres
mkdir -p docker/mongodb
mkdir -p docker/redis
mkdir -p docker/nginx
mkdir -p scripts
mkdir -p logs

# api/v1/endpoints
touch app/api/v1/endpoints/{auth,users,roles,organizations,assets,vulnerabilities,advisories,sources,scrape_jobs,search,health}.py
touch app/api/v1/router.py

# api/dependencies
touch app/api/dependencies/{auth,permissions,pagination,rate_limit,database}.py

# core
touch app/core/{config,security,logging,exceptions,exception_handlers,responses,constants}.py
touch app/core/middleware/{request_logging,error_handling,request_id}.py

# database
touch app/database/{base,session,sync_session,postgres,mongodb}.py

# models
touch app/models/{user,role,organization,asset,vulnerability,advisory,source,scrape_job,audit_log}.py

# schemas
touch app/schemas/{auth,user,role,organization,asset,vulnerability,advisory,source,scrape_job}.py

# repositories
touch app/repositories/postgres/{user_repository,role_repository,organization_repository,asset_repository,vulnerability_repository,source_repository,scrape_job_repository,audit_repository}.py
touch app/repositories/mongo/raw_intel_repository.py

# services
touch app/services/{auth_service,user_service,role_service,organization_service,asset_service,vulnerability_service,advisory_service,source_service,scraping_service,search_service}.py

# scrapers
touch app/scrapers/base/{base_client,base_scraper,parser,cleaner,normalizer,deduplicator}.py
touch app/scrapers/nvd/{client,mapper,config}.py
touch app/scrapers/cisa/{kev_client,advisory_feed,mapper}.py
touch app/scrapers/mitre/{client,mapper}.py
touch app/scrapers/vendor_advisories/redhat/{scraper,selectors,mapper}.py

# tasks
touch app/tasks/{celery_app,scheduler,scrape_tasks,cleanup_tasks}.py

# utils
touch app/utils/{validators,pagination,filters,search,timezone,retry,helpers}.py

# main
touch app/main.py

# tests
touch tests/conftest.py

# docs
touch docs/{architecture,api,database,security,deployment}.md

# root files
touch .env .env.example .gitignore Dockerfile docker-compose.yml requirements.txt pyproject.toml README.md LICENSE

# __init__.py files for every Python package
find app tests -type d -exec touch {}/__init__.py \;

echo "Project structure created."