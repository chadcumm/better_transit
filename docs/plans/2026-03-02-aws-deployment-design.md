# AWS Deployment Design

**Date:** 2026-03-02
**Status:** Approved
**Domain:** nextstopkc.us

## Overview

Deploy the Better Transit FastAPI backend to AWS using SST v3 with GitHub Actions CI/CD. The `develop` branch deploys to `staging.nextstopkc.us` and the `main` branch deploys to `nextstopkc.us`.

## Architecture

```
Route 53 (nextstopkc.us)
  ├── nextstopkc.us           → API Gateway (production)
  └── staging.nextstopkc.us   → API Gateway (staging)

API Gateway v2 (HTTP) + ACM TLS
  └── Lambda (Python 3.12, container image)
        └── FastAPI + Mangum adapter
              └── Neon PostgreSQL + PostGIS (external)

Scheduled Lambda (Cron)
  └── GTFS import — daily at 6 AM CT
```

### Key Decisions

- **SST v3** with Python runtime (community-supported, uses `uv`)
- **Container mode** for Lambda — `geoalchemy2`/`shapely` require native C libraries (`libgeos`, `libproj`)
- **Neon PostgreSQL** — free tier, PostGIS support, serverless scale-to-zero, separate DBs per environment
- **Two SST stages:** `production` (main branch) and `staging` (develop branch)

## SST Configuration

### Components

| Component | Type | Purpose |
|-----------|------|---------|
| Api | `sst.aws.ApiGatewayV2` | HTTP API with custom domain |
| FastApi | `sst.aws.Function` | Python Lambda (container), FastAPI + Mangum |
| GtfsImport | `sst.aws.Cron` | Daily GTFS data refresh (6 AM CT) |
| DatabaseUrl | `sst.Secret` | Neon connection string per stage |
| GtfsRtApiKey | `sst.Secret` | Swiftly RT feed API key |

### Stage-to-Domain Mapping

- `production` stage → `nextstopkc.us`
- Any other stage → `{stage}.nextstopkc.us`

### File Structure

```
infra/
├── sst.config.ts        # Main SST config
├── package.json         # SST + Node dependencies
└── tsconfig.json        # TypeScript config
```

## CI/CD Pipeline (GitHub Actions)

### Workflows

1. **`ci.yml`** — Every PR and push to develop/main
   - `uv run ruff check .`
   - `uv run pytest -m "not slow"`

2. **`deploy-staging.yml`** — Push to `develop` (after CI passes)
   - `npx sst deploy --stage staging`
   - Run `alembic upgrade head` against Neon staging DB

3. **`deploy-production.yml`** — Push to `main` (after CI passes)
   - `npx sst deploy --stage production`
   - Run `alembic upgrade head` against Neon production DB

### GitHub Secrets Required

| Secret | Purpose |
|--------|---------|
| `AWS_ACCESS_KEY_ID` | IAM deploy user |
| `AWS_SECRET_ACCESS_KEY` | IAM deploy user |
| `NEON_STAGING_DATABASE_URL` | Neon staging connection string |
| `NEON_PRODUCTION_DATABASE_URL` | Neon production connection string |
| `GTFS_RT_API_KEY` | Swiftly API key (when available) |

## Code Changes

| File | Change |
|------|--------|
| `api/src/better_transit/handler.py` | New — Mangum wrapper: `handler = Mangum(app)` |
| `api/Dockerfile` | New — Lambda container image (Python 3.12 + system deps) |
| `api/src/better_transit/config.py` | Update default DB URL for Neon SSL |
| `api/src/better_transit/gtfs/importer.py` | Add Lambda handler for cron invocation |
| `api/pyproject.toml` | Add `mangum` dependency |

### Dockerfile

Based on `public.ecr.aws/lambda/python:3.12`:
1. Install system deps: `libgeos`, `libproj` (for shapely/geoalchemy2)
2. Install `uv`, then `uv sync` to install Python dependencies
3. Copy FastAPI app source
4. Set handler to `better_transit.handler.handler`

### Mangum Handler

```python
# api/src/better_transit/handler.py
from mangum import Mangum
from better_transit.main import app

handler = Mangum(app, lifespan="off")
```

### GTFS Cron Handler

```python
# In api/src/better_transit/gtfs/importer.py
def lambda_handler(event, context):
    """Lambda entry point for scheduled GTFS import."""
    import asyncio
    asyncio.run(run_import())
```

## Manual Setup Steps

### 1. Domain Registration (Route 53)

1. Register `nextstopkc.us` in Route 53 (~$16/year)
2. Route 53 creates hosted zone automatically
3. SST handles ACM certificate + DNS validation

### 2. Neon Database Setup

1. Create Neon account at neon.tech
2. Create project: `nextstopkc-staging`
3. Create project: `nextstopkc-production`
4. Enable PostGIS: `CREATE EXTENSION postgis`
5. Copy connection strings to GitHub Secrets
6. Run `alembic upgrade head` against each DB
7. Run initial GTFS import against each DB

### 3. AWS IAM Deploy User

Create an IAM user with permissions for:
- Lambda, API Gateway, CloudFormation, S3 (SST state), IAM (roles), CloudWatch, Route 53, ACM, ECR

### 4. GitHub Secrets

Add all secrets listed above to the repository settings.

## Cost Estimate (Monthly)

| Service | Staging | Production | Notes |
|---------|---------|------------|-------|
| Lambda | ~$0 | ~$0-1 | Pay per request, free tier: 1M requests/mo |
| API Gateway | ~$0 | ~$0-1 | $1 per million requests |
| Neon DB | $0 | $0 | Free tier: 0.5 GB storage, 190 compute hours |
| Route 53 | $0.50 | included | Hosted zone |
| ECR | ~$0 | ~$0 | Container image storage |
| Domain | — | $11/year | nextstopkc.us annual registration |
| **Total** | **~$0.50** | **~$1-2** | **+ $11/year domain** |
