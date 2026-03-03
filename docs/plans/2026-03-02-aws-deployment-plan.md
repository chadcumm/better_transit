# AWS Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy Better Transit FastAPI backend to AWS with SST v3, GitHub Actions CI/CD, and Neon PostgreSQL.

**Architecture:** Lambda (container image) behind API Gateway v2 with custom domain `nextstopkc.app`. Neon PostgreSQL + PostGIS for database. GitHub Actions deploys `develop` → staging, `main` → production.

**Tech Stack:** SST v3 (Ion), AWS Lambda, API Gateway v2, Route 53, Mangum, Neon PostgreSQL, GitHub Actions

**Design Doc:** `docs/plans/2026-03-02-aws-deployment-design.md`

---

## Task 1: Add Mangum Dependency

**Files:**
- Modify: `api/pyproject.toml:6-16`

**Step 1: Add mangum to dependencies**

In `api/pyproject.toml`, add `mangum` to the dependencies list:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "mangum>=0.19.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "uvicorn>=0.34.0",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "geoalchemy2>=0.15.0",
    "shapely>=2.0",
    "gtfs-realtime-bindings>=2.0.0",
]
```

**Step 2: Install the dependency**

Run: `cd api && uv sync`
Expected: mangum installed successfully

**Step 3: Verify import works**

Run: `cd api && uv run python -c "import mangum; print(mangum.__version__)"`
Expected: Version number printed (0.19.x)

**Step 4: Commit**

```bash
cd api && git add pyproject.toml uv.lock
git commit -m "feat: add mangum dependency for Lambda ASGI adapter"
```

---

## Task 2: Create Mangum Lambda Handler

**Files:**
- Create: `api/src/better_transit/handler.py`
- Test: `api/tests/test_handler.py`

**Step 1: Write the test**

Create `api/tests/test_handler.py`:

```python
"""Tests for Lambda handler."""

from unittest.mock import patch


def test_handler_is_callable():
    from better_transit.handler import handler

    assert callable(handler)


@patch("better_transit.handler.Mangum.__call__")
def test_handler_wraps_app(mock_call):
    """Handler delegates to Mangum which wraps the FastAPI app."""
    from better_transit.handler import handler
    from better_transit.main import app

    # Verify handler is a Mangum instance wrapping our app
    assert handler.app is app
```

**Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/test_handler.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'better_transit.handler'`

**Step 3: Write the handler**

Create `api/src/better_transit/handler.py`:

```python
"""AWS Lambda handler — wraps the FastAPI app with Mangum."""

from mangum import Mangum

from better_transit.main import app

handler = Mangum(app, lifespan="off")
```

**Step 4: Run test to verify it passes**

Run: `cd api && uv run pytest tests/test_handler.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add api/src/better_transit/handler.py api/tests/test_handler.py
git commit -m "feat: add Mangum Lambda handler for FastAPI"
```

---

## Task 3: Add Lambda Handler for GTFS Cron Import

**Files:**
- Modify: `api/src/better_transit/gtfs/importer.py:55-65`
- Test: `api/tests/gtfs/test_importer.py`

**Step 1: Write the test**

Add to `api/tests/gtfs/test_importer.py`:

```python
from unittest.mock import AsyncMock, patch


@patch("better_transit.gtfs.importer.run_import", new_callable=AsyncMock)
@patch("better_transit.gtfs.importer.create_async_engine")
def test_lambda_handler(mock_engine, mock_run_import):
    """Lambda handler creates engine from settings and runs import."""
    mock_run_import.return_value = {"agency": 1}
    mock_dispose = AsyncMock()
    mock_engine.return_value.dispose = mock_dispose

    from better_transit.gtfs.importer import lambda_handler

    result = lambda_handler({}, None)

    mock_engine.assert_called_once()
    mock_run_import.assert_called_once()
    assert result["statusCode"] == 200
```

**Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/gtfs/test_importer.py::test_lambda_handler -v`
Expected: FAIL — `ImportError: cannot import name 'lambda_handler'`

**Step 3: Add lambda_handler to importer.py**

Add after the `_main()` function in `api/src/better_transit/gtfs/importer.py`:

```python
def lambda_handler(event, context):
    """AWS Lambda entry point for scheduled GTFS import."""
    import asyncio
    import json

    async def _run():
        engine = create_async_engine(settings.database_url)
        try:
            stats = await run_import(engine)
            return stats
        finally:
            await engine.dispose()

    stats = asyncio.run(_run())
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "GTFS import complete", "stats": stats}),
    }
```

**Step 4: Run test to verify it passes**

Run: `cd api && uv run pytest tests/gtfs/test_importer.py -v`
Expected: All tests pass

**Step 5: Run full test suite**

Run: `cd api && uv run pytest -m "not slow" -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add api/src/better_transit/gtfs/importer.py api/tests/gtfs/test_importer.py
git commit -m "feat: add Lambda handler for scheduled GTFS import"
```

---

## Task 4: Create Dockerfile for Lambda Container

**Files:**
- Create: `api/Dockerfile`
- Create: `api/.dockerignore`

**Step 1: Create .dockerignore**

Create `api/.dockerignore`:

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
tests/
.env
*.md
```

**Step 2: Create the Dockerfile**

Create `api/Dockerfile`:

```dockerfile
FROM public.ecr.aws/lambda/python:3.12

# Install system dependencies for geoalchemy2/shapely
RUN dnf install -y geos geos-devel proj proj-devel && dnf clean all

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no dev deps)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY src/ src/
COPY migrations/ migrations/
COPY alembic.ini .

# Install the project itself
RUN uv sync --frozen --no-dev

# Set the Lambda handler
CMD ["better_transit.handler.handler"]
```

**Step 3: Verify the Docker build works**

Run: `cd api && docker build -t better-transit-lambda .`
Expected: Build completes successfully

**Step 4: Commit**

```bash
git add api/Dockerfile api/.dockerignore
git commit -m "feat: add Dockerfile for Lambda container image"
```

---

## Task 5: Initialize SST v3 Infrastructure

**Files:**
- Create: `infra/package.json`
- Create: `infra/tsconfig.json`
- Create: `infra/sst.config.ts`

**Step 1: Initialize SST project**

```bash
cd /Users/chadcummings/Github/better_transit/infra
npm init -y
npm install sst@latest
```

**Step 2: Create tsconfig.json**

Create `infra/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  }
}
```

**Step 3: Create sst.config.ts**

Create `infra/sst.config.ts`:

```typescript
/// <reference path="./.sst/platform/config.d.ts" />

export default $config({
  app(input) {
    return {
      name: "nextstopkc",
      removal: input?.stage === "production" ? "retain" : "remove",
      home: "aws",
      providers: {
        aws: {
          region: "us-east-1",
        },
      },
    };
  },
  async run() {
    // --- Secrets ---
    const databaseUrl = new sst.Secret("DatabaseUrl");
    const gtfsRtApiKey = new sst.Secret("GtfsRtApiKey");

    // --- Domain ---
    const domain =
      $app.stage === "production"
        ? "nextstopkc.app"
        : `${$app.stage}.nextstopkc.app`;

    // --- API Gateway + Lambda ---
    const api = new sst.aws.ApiGatewayV2("Api", {
      domain: {
        name: domain,
        dns: sst.aws.dns(),
      },
      cors: {
        allowOrigins: ["*"],
        allowMethods: ["GET", "POST", "OPTIONS"],
        allowHeaders: ["content-type"],
      },
    });

    const apiFn = new sst.aws.Function("FastApi", {
      runtime: "python3.12",
      handler: "src/better_transit/handler.handler",
      url: false,
      timeout: "30 seconds",
      memory: "512 MB",
      python: {
        container: true,
      },
      environment: {
        DATABASE_URL: databaseUrl.value,
        GTFS_RT_API_KEY: gtfsRtApiKey.value,
      },
      link: [databaseUrl, gtfsRtApiKey],
    });

    // Route all requests to the FastAPI Lambda
    api.route("$default", apiFn.arn);

    // --- Scheduled GTFS Import ---
    new sst.aws.Cron("GtfsImport", {
      schedule: "cron(0 12 * * ? *)", // 12:00 UTC = 6:00 AM CT
      function: {
        runtime: "python3.12",
        handler: "src/better_transit/gtfs/importer.lambda_handler",
        timeout: "300 seconds",
        memory: "1024 MB",
        python: {
          container: true,
        },
        environment: {
          DATABASE_URL: databaseUrl.value,
        },
        link: [databaseUrl],
      },
    });

    return {
      api: api.url,
      domain: domain,
    };
  },
});
```

**Step 4: Verify SST config is valid**

Run: `cd infra && npx sst version`
Expected: SST version printed

**Step 5: Commit**

```bash
git add infra/package.json infra/package-lock.json infra/tsconfig.json infra/sst.config.ts
git commit -m "feat: add SST v3 infrastructure config"
```

---

## Task 6: Create GitHub Actions CI Workflow

**Files:**
- Create: `.github/workflows/ci.yml`

**Step 1: Create CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main, develop]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: api

    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync --frozen

      - name: Lint
        run: uv run ruff check .

      - name: Test
        run: uv run pytest -m "not slow" -v
```

**Step 2: Commit**

```bash
mkdir -p .github/workflows
git add .github/workflows/ci.yml
git commit -m "ci: add lint and test workflow"
```

---

## Task 7: Create GitHub Actions Deploy Workflows

**Files:**
- Create: `.github/workflows/deploy-staging.yml`
- Create: `.github/workflows/deploy-production.yml`

**Step 1: Create staging deploy workflow**

Create `.github/workflows/deploy-staging.yml`:

```yaml
name: Deploy Staging

on:
  push:
    branches: [develop]

concurrency:
  group: deploy-staging
  cancel-in-progress: true

jobs:
  ci:
    uses: ./.github/workflows/ci.yml

  deploy:
    needs: ci
    runs-on: ubuntu-latest
    environment: staging
    permissions:
      id-token: write
      contents: read

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"

      - uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install SST dependencies
        working-directory: infra
        run: npm ci

      - name: Set SST secrets
        working-directory: infra
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          npx sst secret set DatabaseUrl "${{ secrets.NEON_STAGING_DATABASE_URL }}" --stage staging
          npx sst secret set GtfsRtApiKey "${{ secrets.GTFS_RT_API_KEY }}" --stage staging

      - name: Deploy to staging
        working-directory: infra
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: npx sst deploy --stage staging

      - name: Run database migrations
        working-directory: api
        env:
          DATABASE_URL: ${{ secrets.NEON_STAGING_DATABASE_URL }}
        run: |
          uv sync --frozen --no-dev
          uv run alembic upgrade head
```

**Step 2: Create production deploy workflow**

Create `.github/workflows/deploy-production.yml`:

```yaml
name: Deploy Production

on:
  push:
    branches: [main]

concurrency:
  group: deploy-production
  cancel-in-progress: false

jobs:
  ci:
    uses: ./.github/workflows/ci.yml

  deploy:
    needs: ci
    runs-on: ubuntu-latest
    environment: production
    permissions:
      id-token: write
      contents: read

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"

      - uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install SST dependencies
        working-directory: infra
        run: npm ci

      - name: Set SST secrets
        working-directory: infra
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          npx sst secret set DatabaseUrl "${{ secrets.NEON_PRODUCTION_DATABASE_URL }}" --stage production
          npx sst secret set GtfsRtApiKey "${{ secrets.GTFS_RT_API_KEY }}" --stage production

      - name: Deploy to production
        working-directory: infra
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: npx sst deploy --stage production

      - name: Run database migrations
        working-directory: api
        env:
          DATABASE_URL: ${{ secrets.NEON_PRODUCTION_DATABASE_URL }}
        run: |
          uv sync --frozen --no-dev
          uv run alembic upgrade head
```

**Step 3: Commit**

```bash
git add .github/workflows/deploy-staging.yml .github/workflows/deploy-production.yml
git commit -m "ci: add staging and production deploy workflows"
```

---

## Task 8: Update Config for Neon SSL Compatibility

**Files:**
- Modify: `api/src/better_transit/config.py`

**Step 1: Update default database URL**

The config reads `DATABASE_URL` from environment. Neon requires `sslmode=require`. Update the default to keep local dev working while documenting the expected format:

In `api/src/better_transit/config.py`, change the `database_url` field name to match the environment variable SST sets:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://better_transit:dev@localhost:5432/better_transit"
    )
    gtfs_static_url: str = "https://www.kc-metro.com/gtf/google_transit.zip"

    # GTFS-RT via Swiftly
    gtfs_rt_api_key: str = ""
    gtfs_rt_trip_updates_url: str = (
        "https://api.goswift.ly/real-time/kcata/gtfs-rt-trip-updates"
    )
    gtfs_rt_vehicle_positions_url: str = (
        "https://api.goswift.ly/real-time/kcata/gtfs-rt-vehicle-positions"
    )
    gtfs_rt_service_alerts_url: str = (
        "https://api.goswift.ly/real-time/kcata/gtfs-rt-service-alerts"
    )

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
```

No code change is actually needed here — `pydantic-settings` already reads `DATABASE_URL` from env vars (case-insensitive matching). The Neon connection string set via SST secret will override the default. The `sslmode=require` parameter is part of the Neon connection string itself.

**Step 2: Update .env.example to document Neon format**

In `api/.env.example`, add a comment showing the Neon format:

```
# Local development
DATABASE_URL=postgresql+asyncpg://better_transit:dev@localhost:5432/better_transit

# Neon (staging/production) — set via SST secrets, format:
# DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.us-east-1.aws.neon.tech/dbname?sslmode=require
```

**Step 3: Run tests to verify nothing broke**

Run: `cd api && uv run pytest -m "not slow" -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add api/.env.example
git commit -m "docs: document Neon connection string format in .env.example"
```

---

## Task 9: Create develop Branch

**Files:** None (git operations only)

**Step 1: Create and push develop branch**

```bash
git checkout -b develop
git push -u origin develop
```

**Step 2: Verify branch exists**

Run: `git branch -a`
Expected: Both `main` and `develop` branches listed

---

## Task 10: Manual Setup — Domain, Neon, GitHub Secrets

This task is manual — no code changes. Follow these steps in order:

### 10a: Register Domain in Route 53

1. Go to AWS Console → Route 53 → Registered Domains
2. Register `nextstopkc.app` (~$16/year)
3. Wait for registration to complete (can take up to 15 minutes)
4. Verify hosted zone was created: Route 53 → Hosted Zones → `nextstopkc.app`

### 10b: Set Up Neon Databases

1. Go to https://neon.tech and create an account
2. Create project: `nextstopkc-staging`
   - Region: AWS us-east-1 (matches Lambda)
   - Copy connection string (Dashboard → Connect → Connection string)
3. Create project: `nextstopkc-production`
   - Region: AWS us-east-1
   - Copy connection string
4. For each project, run in the Neon SQL Editor:
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   ```
5. Convert connection strings to asyncpg format:
   - Change `postgresql://` to `postgresql+asyncpg://`
   - Ensure `?sslmode=require` is at the end

### 10c: Run Initial Migrations and GTFS Import

For each database (staging and production):

```bash
cd api
DATABASE_URL="postgresql+asyncpg://user:pass@ep-xxx.neon.tech/dbname?sslmode=require" uv run alembic upgrade head
DATABASE_URL="postgresql+asyncpg://user:pass@ep-xxx.neon.tech/dbname?sslmode=require" uv run python -m better_transit.gtfs.importer
```

### 10d: Create AWS IAM Deploy User

1. AWS Console → IAM → Users → Create User: `nextstopkc-deploy`
2. Attach policy: `AdministratorAccess` (for initial setup; tighten later)
3. Create Access Key → save `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`

### 10e: Add GitHub Repository Secrets

Go to GitHub repo → Settings → Secrets and variables → Actions:

| Secret | Value |
|--------|-------|
| `AWS_ACCESS_KEY_ID` | From IAM user |
| `AWS_SECRET_ACCESS_KEY` | From IAM user |
| `NEON_STAGING_DATABASE_URL` | Neon staging asyncpg connection string |
| `NEON_PRODUCTION_DATABASE_URL` | Neon production asyncpg connection string |
| `GTFS_RT_API_KEY` | Swiftly API key (leave empty if not available yet) |

---

## Task 11: First Deploy — Staging

**Step 1: Deploy staging locally to verify SST config works**

```bash
cd infra
npx sst secret set DatabaseUrl "YOUR_NEON_STAGING_URL" --stage staging
npx sst secret set GtfsRtApiKey "" --stage staging
npx sst deploy --stage staging
```

Expected: SST creates API Gateway, Lambda, Cron, and DNS records. Outputs API URL.

**Step 2: Test the staging deployment**

```bash
curl https://staging.nextstopkc.app/health
```

Expected: `{"status":"ok"}`

```bash
curl "https://staging.nextstopkc.app/routes"
```

Expected: JSON array of KCATA routes

**Step 3: Test the GitHub Actions pipeline**

```bash
git checkout develop
# Make a trivial change (e.g., bump version in pyproject.toml)
git add -A && git commit -m "test: trigger staging deploy"
git push
```

Expected: GitHub Actions runs CI → Deploy Staging → success

---

## Task 12: First Deploy — Production

**Step 1: Merge develop to main**

```bash
git checkout main
git merge develop
git push
```

Expected: GitHub Actions runs CI → Deploy Production → success

**Step 2: Test the production deployment**

```bash
curl https://nextstopkc.app/health
```

Expected: `{"status":"ok"}`

```bash
curl "https://nextstopkc.app/stops/nearby?lat=39.0997&lon=-94.5786&radius=500"
```

Expected: JSON array of nearby stops with arrival times

---

## Verification Checklist

After all tasks complete, verify:

- [ ] `nextstopkc.app/health` returns `{"status":"ok"}`
- [ ] `staging.nextstopkc.app/health` returns `{"status":"ok"}`
- [ ] `nextstopkc.app/routes` returns 36 KCATA routes
- [ ] `nextstopkc.app/stops/nearby?lat=39.0997&lon=-94.5786&radius=500` returns nearby stops
- [ ] Push to `develop` triggers staging deploy
- [ ] Push to `main` triggers production deploy
- [ ] GTFS cron runs daily at 6 AM CT (check CloudWatch logs after 24h)
