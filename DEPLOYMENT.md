# WealthWise Finance Tracker — Deployment Guide

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Environment Variables](#environment-variables)
4. [Vercel Configuration](#vercel-configuration)
5. [Build Steps](#build-steps)
6. [Database Considerations for Serverless](#database-considerations-for-serverless)
7. [Local Development](#local-development)
8. [Troubleshooting](#troubleshooting)

---

## Overview

WealthWise Finance Tracker is a Python 3.11+ FastAPI application. This guide covers deploying the application to **Vercel** as a serverless function, including configuration, environment setup, and important caveats around database usage in a serverless environment.

---

## Prerequisites

- **Python 3.11+** installed locally for development and testing
- **Vercel CLI** installed globally: `npm install -g vercel`
- A **Vercel account** linked to your Git provider (GitHub, GitLab, or Bitbucket)
- A `.env` file configured locally (see [Environment Variables](#environment-variables))

---

## Environment Variables

Create a `.env` file in the project root for local development. For Vercel, set these in the Vercel Dashboard under **Project Settings → Environment Variables**.

| Variable | Required | Description | Example |
|---|---|---|---|
| `SECRET_KEY` | Yes | Secret key for JWT signing and session security. Must be a long random string. | `openssl rand -hex 32` |
| `DATABASE_URL` | Yes | Database connection string. See [Database Considerations](#database-considerations-for-serverless). | `sqlite+aiosqlite:///./wealthwise.db` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | JWT access token lifetime in minutes. Defaults to `30`. | `60` |
| `ALGORITHM` | No | JWT signing algorithm. Defaults to `HS256`. | `HS256` |
| `CORS_ORIGINS` | No | Comma-separated list of allowed CORS origins. Defaults to `*` in dev. | `https://yourdomain.com,https://www.yourdomain.com` |
| `ENVIRONMENT` | No | Deployment environment identifier. | `production` |
| `DEBUG` | No | Enable debug mode. Defaults to `false`. | `false` |

### Setting Environment Variables on Vercel

1. Navigate to your project on the [Vercel Dashboard](https://vercel.com/dashboard).
2. Go to **Settings → Environment Variables**.
3. Add each variable listed above.
4. Select the appropriate scope: **Production**, **Preview**, and/or **Development**.
5. Click **Save**.

> **Security Note:** Never commit your `.env` file to version control. Ensure `.env` is listed in `.gitignore`.

---

## Vercel Configuration

Create a `vercel.json` file in the project root:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "app/main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "app/main.py"
    }
  ],
  "env": {
    "ENVIRONMENT": "production"
  }
}
```

### Key Points

- **`builds`**: Tells Vercel to use the Python runtime and points to the FastAPI entry point.
- **`routes`**: Catches all incoming requests and routes them to the FastAPI application.
- **`@vercel/python`**: Vercel's Python serverless function builder. It automatically detects `requirements.txt` and installs dependencies.

### Required File: `requirements.txt`

Vercel reads `requirements.txt` from the project root to install Python dependencies. Ensure this file is present and up to date. Run the following locally to verify all dependencies resolve:

```bash
pip install -r requirements.txt
```

---

## Build Steps

### Deploying via Vercel CLI

```bash
# 1. Login to Vercel (first time only)
vercel login

# 2. Link your project (first time only)
vercel link

# 3. Deploy to preview
vercel

# 4. Deploy to production
vercel --prod
```

### Deploying via Git Integration

1. Push your code to the connected Git repository.
2. Vercel automatically detects the push and triggers a build.
3. Preview deployments are created for pull requests / merge requests.
4. Merges to the production branch (usually `main`) trigger a production deployment.

### Build Process Summary

1. Vercel detects `requirements.txt` and installs all Python dependencies.
2. Vercel packages `app/main.py` as a serverless function using `@vercel/python`.
3. All routes are directed to the FastAPI application via `vercel.json` route configuration.
4. Static files in `app/templates/` and `app/static/` are bundled with the function.

---

## Database Considerations for Serverless

### SQLite Limitations on Vercel

**SQLite is NOT recommended for production deployments on Vercel.** Here is why:

| Issue | Explanation |
|---|---|
| **Ephemeral filesystem** | Vercel serverless functions have a read-only filesystem (except `/tmp`). SQLite databases written to `/tmp` are lost when the function cold-starts or scales. |
| **No shared state** | Each serverless function invocation may run in a separate container. There is no shared filesystem between invocations, so concurrent requests may see different database states. |
| **Data loss** | Any data written to SQLite in `/tmp` is not persisted across deployments or cold starts. |

### Recommended: Use a Hosted Database

For production, replace SQLite with a hosted database service:

#### Option 1: PostgreSQL (Recommended)

Use a managed PostgreSQL provider such as:

- **Vercel Postgres** (native integration)
- **Supabase** (free tier available)
- **Neon** (serverless Postgres, free tier available)
- **Railway** or **Render** (managed Postgres)

Update your `DATABASE_URL`:

```
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/wealthwise
```

Add `asyncpg` to `requirements.txt`:

```
asyncpg>=0.29.0
```

#### Option 2: Turso (libSQL — SQLite-compatible, serverless-friendly)

[Turso](https://turso.tech/) provides a hosted, replicated SQLite-compatible database that works well with serverless:

```
DATABASE_URL=libsql://your-db-name-your-org.turso.io?authToken=your-token
```

#### Option 3: SQLite for Development Only

For local development and testing, SQLite with aiosqlite works well:

```
DATABASE_URL=sqlite+aiosqlite:///./wealthwise.db
```

This is the default and requires no additional setup for local development.

### Migration Strategy

When switching from SQLite to PostgreSQL:

1. Update `DATABASE_URL` in your environment variables.
2. Update `requirements.txt` to include the appropriate async driver (`asyncpg` for PostgreSQL).
3. Run database migrations (if using Alembic):
   ```bash
   alembic upgrade head
   ```
4. Test all endpoints against the new database before deploying to production.

---

## Local Development

### Setup

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd wealthwise-finance-tracker

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your .env file
cp .env.example .env
# Edit .env with your configuration

# 5. Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_auth.py

# Run async tests (requires pytest-asyncio)
pytest --asyncio-mode=auto
```

---

## Troubleshooting

### Common Issues

#### 1. `ModuleNotFoundError: No module named 'app'`

**Cause:** Vercel cannot resolve the Python module path.

**Fix:** Ensure your `vercel.json` points to the correct entry file (`app/main.py`) and that `app/__init__.py` exists. Verify the project structure matches:

```
project-root/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── core/
│   ├── models/
│   ├── routers/
│   ├── schemas/
│   ├── services/
│   └── templates/
├── requirements.txt
├── vercel.json
└── .env
```

#### 2. `ImportError: email-validator is not installed`

**Cause:** A Pydantic schema uses `EmailStr` but `email-validator` is missing from `requirements.txt`.

**Fix:** Add `email-validator>=2.1.0` to `requirements.txt`.

#### 3. `500 Internal Server Error` on all routes

**Cause:** Often a missing or misconfigured environment variable.

**Fix:**
- Check Vercel function logs: **Vercel Dashboard → Deployments → Functions → Logs**.
- Verify all required environment variables are set (especially `SECRET_KEY` and `DATABASE_URL`).
- Ensure `DATABASE_URL` uses a hosted database, not a local SQLite path.

#### 4. `TemplateNotFound` error

**Cause:** Jinja2 cannot locate template files because the templates directory path is relative and the working directory differs on Vercel.

**Fix:** Ensure template directory resolution uses absolute paths:

```python
from pathlib import Path
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent / "templates")
)
```

#### 5. `MissingGreenlet: greenlet_spawn has not been called`

**Cause:** SQLAlchemy lazy loading is triggered inside an async context.

**Fix:** Ensure all `relationship()` declarations use `lazy="selectin"` and queries use `selectinload()` for relationships accessed in templates or response serialization.

#### 6. Database is empty after redeployment

**Cause:** SQLite on Vercel's ephemeral filesystem. Data in `/tmp` does not persist.

**Fix:** Migrate to a hosted database (see [Database Considerations](#database-considerations-for-serverless)).

#### 7. CORS errors in the browser

**Cause:** The frontend origin is not in the allowed CORS origins list.

**Fix:** Set the `CORS_ORIGINS` environment variable to include your frontend domain:

```
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

#### 8. `422 Unprocessable Entity` on form submissions

**Cause:** Form field names in the HTML template do not match the FastAPI `Form()` parameter names, or `python-multipart` is not installed.

**Fix:**
- Verify `python-multipart` is in `requirements.txt`.
- Ensure every `<input name="X">` in templates matches a corresponding `X: str = Form(...)` in the route handler.

#### 9. Cold start timeouts

**Cause:** Vercel serverless functions have a default timeout (10s on Hobby, 60s on Pro). Heavy initialization (large model loading, slow DB connections) can exceed this.

**Fix:**
- Minimize startup work in the lifespan handler.
- Use connection pooling for database connections.
- Consider upgrading to Vercel Pro for longer timeouts.

#### 10. `bcrypt` / `passlib` errors

**Cause:** Incompatible `bcrypt` version with `passlib`.

**Fix:** Pin `bcrypt==4.0.1` in `requirements.txt`, or use `bcrypt` directly without `passlib`:

```python
import bcrypt
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
valid = bcrypt.checkpw(password.encode(), hashed.encode())
```

### Viewing Logs on Vercel

1. Go to the [Vercel Dashboard](https://vercel.com/dashboard).
2. Select your project.
3. Navigate to **Deployments** → select a deployment.
4. Click **Functions** to see serverless function logs.
5. Use **Runtime Logs** for real-time log streaming during debugging.

### Getting Help

- **FastAPI Documentation:** [https://fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **Vercel Python Runtime:** [https://vercel.com/docs/functions/runtimes/python](https://vercel.com/docs/functions/runtimes/python)
- **SQLAlchemy Async:** [https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- **Pydantic v2:** [https://docs.pydantic.dev/latest/](https://docs.pydantic.dev/latest/)