# WealthWise Finance Tracker

A comprehensive personal finance tracking API built with Python 3.11+ and FastAPI. Track income, expenses, budgets, and financial goals with powerful analytics and reporting.

## Features

- **User Authentication** — Secure JWT-based registration, login, and token refresh
- **Account Management** — Create and manage multiple financial accounts (checking, savings, credit, investment)
- **Transaction Tracking** — Record income and expenses with categories, tags, and notes
- **Budget Management** — Set monthly/weekly budgets per category with overspend alerts
- **Financial Goals** — Define savings goals and track progress over time
- **Category Management** — Custom transaction categories with icons and color coding
- **Analytics & Reports** — Spending breakdowns, income vs. expense trends, and net worth calculations
- **Recurring Transactions** — Automate repeating income/expense entries
- **CSV Import/Export** — Bulk import transactions or export data for external use
- **Multi-currency Support** — Track finances across different currencies

## Tech Stack

- **Runtime:** Python 3.11+
- **Framework:** FastAPI
- **Database:** SQLite (via aiosqlite for async) / PostgreSQL (via asyncpg for production)
- **ORM:** SQLAlchemy 2.0 (async)
- **Authentication:** JWT (python-jose) + bcrypt password hashing
- **Validation:** Pydantic v2
- **Configuration:** pydantic-settings with `.env` support
- **Testing:** pytest + pytest-asyncio + httpx

## Project Structure

```
wealthwise-finance-tracker/
├── app/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # Application settings (BaseSettings)
│   │   ├── database.py        # Async SQLAlchemy engine & session
│   │   └── security.py        # JWT token creation/verification, password hashing
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py            # User model
│   │   ├── account.py         # Financial account model
│   │   ├── transaction.py     # Transaction model
│   │   ├── category.py        # Category model
│   │   ├── budget.py          # Budget model
│   │   └── goal.py            # Financial goal model
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py            # User request/response schemas
│   │   ├── account.py         # Account schemas
│   │   ├── transaction.py     # Transaction schemas
│   │   ├── category.py        # Category schemas
│   │   ├── budget.py          # Budget schemas
│   │   └── goal.py            # Goal schemas
│   ├── services/
│   │   ├── __init__.py
│   │   ├── user_service.py    # User business logic
│   │   ├── account_service.py # Account business logic
│   │   ├── transaction_service.py # Transaction business logic
│   │   ├── budget_service.py  # Budget business logic
│   │   └── goal_service.py    # Goal business logic
│   ├── dependencies/
│   │   ├── __init__.py
│   │   └── auth.py            # Authentication dependencies (get_current_user)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py            # Auth endpoints (register, login, refresh)
│   │   ├── users.py           # User profile endpoints
│   │   ├── accounts.py        # Account CRUD endpoints
│   │   ├── transactions.py    # Transaction CRUD + filtering endpoints
│   │   ├── categories.py      # Category CRUD endpoints
│   │   ├── budgets.py         # Budget CRUD endpoints
│   │   ├── goals.py           # Goal CRUD endpoints
│   │   └── analytics.py       # Analytics/reporting endpoints
│   └── main.py                # FastAPI app entry point
├── tests/
│   ├── conftest.py            # Shared fixtures (async client, test DB)
│   ├── test_auth.py           # Auth endpoint tests
│   ├── test_accounts.py       # Account endpoint tests
│   ├── test_transactions.py   # Transaction endpoint tests
│   ├── test_budgets.py        # Budget endpoint tests
│   └── test_goals.py          # Goal endpoint tests
├── .env.example               # Environment variable template
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Getting Started

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Git

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-org/wealthwise-finance-tracker.git
   cd wealthwise-finance-tracker
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate        # macOS/Linux
   venv\Scripts\activate           # Windows
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your settings:

   ```env
   DATABASE_URL=sqlite+aiosqlite:///./wealthwise.db
   SECRET_KEY=your-super-secret-key-change-in-production
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   REFRESH_TOKEN_EXPIRE_DAYS=7
   CORS_ORIGINS=["http://localhost:3000"]
   ```

5. **Run database migrations (auto-create tables on first startup):**

   The application automatically creates all database tables on startup via the lifespan handler. No manual migration step is required for initial setup.

6. **Start the development server:**

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   The API will be available at `http://localhost:8000`.

7. **Access interactive API docs:**

   - **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Running Tests

```bash
pytest -v
```

Run with coverage:

```bash
pytest --cov=app --cov-report=term-missing -v
```

## API Endpoint Reference

### Authentication

| Method | Endpoint              | Description              | Auth Required |
|--------|-----------------------|--------------------------|---------------|
| POST   | `/api/auth/register`  | Register a new user      | No            |
| POST   | `/api/auth/login`     | Login and get tokens     | No            |
| POST   | `/api/auth/refresh`   | Refresh access token     | Yes           |

### Users

| Method | Endpoint              | Description              | Auth Required |
|--------|-----------------------|--------------------------|---------------|
| GET    | `/api/users/me`       | Get current user profile | Yes           |
| PUT    | `/api/users/me`       | Update current user      | Yes           |
| DELETE | `/api/users/me`       | Delete current user      | Yes           |

### Accounts

| Method | Endpoint                  | Description              | Auth Required |
|--------|---------------------------|--------------------------|---------------|
| GET    | `/api/accounts`           | List all accounts        | Yes           |
| POST   | `/api/accounts`           | Create a new account     | Yes           |
| GET    | `/api/accounts/{id}`      | Get account details      | Yes           |
| PUT    | `/api/accounts/{id}`      | Update an account        | Yes           |
| DELETE | `/api/accounts/{id}`      | Delete an account        | Yes           |

### Transactions

| Method | Endpoint                      | Description                        | Auth Required |
|--------|-------------------------------|------------------------------------|---------------|
| GET    | `/api/transactions`           | List transactions (with filters)   | Yes           |
| POST   | `/api/transactions`           | Create a new transaction           | Yes           |
| GET    | `/api/transactions/{id}`      | Get transaction details            | Yes           |
| PUT    | `/api/transactions/{id}`      | Update a transaction               | Yes           |
| DELETE | `/api/transactions/{id}`      | Delete a transaction               | Yes           |

**Query Parameters for GET `/api/transactions`:**
- `account_id` — Filter by account
- `category_id` — Filter by category
- `type` — Filter by type (`income` or `expense`)
- `start_date` — Filter from date (ISO 8601)
- `end_date` — Filter to date (ISO 8601)
- `min_amount` — Minimum amount filter
- `max_amount` — Maximum amount filter
- `skip` — Pagination offset (default: 0)
- `limit` — Pagination limit (default: 50, max: 100)

### Categories

| Method | Endpoint                    | Description              | Auth Required |
|--------|-----------------------------|--------------------------|---------------|
| GET    | `/api/categories`           | List all categories      | Yes           |
| POST   | `/api/categories`           | Create a new category    | Yes           |
| GET    | `/api/categories/{id}`      | Get category details     | Yes           |
| PUT    | `/api/categories/{id}`      | Update a category        | Yes           |
| DELETE | `/api/categories/{id}`      | Delete a category        | Yes           |

### Budgets

| Method | Endpoint                  | Description              | Auth Required |
|--------|---------------------------|--------------------------|---------------|
| GET    | `/api/budgets`            | List all budgets         | Yes           |
| POST   | `/api/budgets`            | Create a new budget      | Yes           |
| GET    | `/api/budgets/{id}`       | Get budget details       | Yes           |
| PUT    | `/api/budgets/{id}`       | Update a budget          | Yes           |
| DELETE | `/api/budgets/{id}`       | Delete a budget          | Yes           |

### Goals

| Method | Endpoint                | Description              | Auth Required |
|--------|-------------------------|--------------------------|---------------|
| GET    | `/api/goals`            | List all goals           | Yes           |
| POST   | `/api/goals`            | Create a new goal        | Yes           |
| GET    | `/api/goals/{id}`       | Get goal details         | Yes           |
| PUT    | `/api/goals/{id}`       | Update a goal            | Yes           |
| DELETE | `/api/goals/{id}`       | Delete a goal            | Yes           |

### Analytics

| Method | Endpoint                              | Description                          | Auth Required |
|--------|---------------------------------------|--------------------------------------|---------------|
| GET    | `/api/analytics/spending-by-category` | Spending breakdown by category       | Yes           |
| GET    | `/api/analytics/income-vs-expenses`   | Income vs. expenses over time        | Yes           |
| GET    | `/api/analytics/net-worth`            | Net worth calculation across accounts| Yes           |
| GET    | `/api/analytics/monthly-summary`      | Monthly income/expense summary       | Yes           |

## Deployment

### Vercel Deployment

1. **Install the Vercel CLI:**

   ```bash
   npm install -g vercel
   ```

2. **Create a `vercel.json` in the project root:**

   ```json
   {
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
     ]
   }
   ```

3. **Set environment variables in Vercel dashboard:**

   Navigate to your project settings → Environment Variables and add:
   - `DATABASE_URL` — Your production database connection string (PostgreSQL recommended)
   - `SECRET_KEY` — A strong random secret key
   - `ACCESS_TOKEN_EXPIRE_MINUTES` — Token expiry (e.g., `30`)
   - `REFRESH_TOKEN_EXPIRE_DAYS` — Refresh token expiry (e.g., `7`)
   - `CORS_ORIGINS` — Allowed origins as JSON array

4. **Deploy:**

   ```bash
   vercel --prod
   ```

### Docker Deployment (Alternative)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t wealthwise-finance-tracker .
docker run -p 8000:8000 --env-file .env wealthwise-finance-tracker
```

## Environment Variables

| Variable                      | Description                        | Default                                  |
|-------------------------------|------------------------------------|------------------------------------------|
| `DATABASE_URL`                | Database connection string         | `sqlite+aiosqlite:///./wealthwise.db`    |
| `SECRET_KEY`                  | JWT signing secret                 | (required — no default)                  |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL in minutes        | `30`                                     |
| `REFRESH_TOKEN_EXPIRE_DAYS`   | Refresh token TTL in days          | `7`                                      |
| `CORS_ORIGINS`                | Allowed CORS origins (JSON array)  | `["http://localhost:3000"]`              |

## License

Private — All rights reserved.