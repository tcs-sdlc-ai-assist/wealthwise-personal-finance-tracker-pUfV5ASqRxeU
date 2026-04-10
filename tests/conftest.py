import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from database import Base, get_db
from main import app
from models.user import User
from models.category import Category
from models.transaction import Transaction
from models.budget import Budget
from utils.security import hash_password, create_access_token


TEST_DATABASE_URL = "sqlite:///./test_wealthwise.db"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def db():
    """Provide a database session for tests."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client():
    """Provide a test client for the FastAPI app."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def test_user(db: Session) -> User:
    """Create and return a regular test user."""
    now = datetime.now(timezone.utc)
    user = User(
        id=str(uuid.uuid4()),
        username="testuser",
        email="testuser@example.com",
        full_name="Test User",
        password_hash=hash_password("TestPass123"),
        role="user",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_user(db: Session) -> User:
    """Create and return an admin test user."""
    now = datetime.now(timezone.utc)
    user = User(
        id=str(uuid.uuid4()),
        username="adminuser",
        email="admin@example.com",
        full_name="Admin User",
        password_hash=hash_password("AdminPass123"),
        role="admin",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def inactive_user(db: Session) -> User:
    """Create and return an inactive test user."""
    now = datetime.now(timezone.utc)
    user = User(
        id=str(uuid.uuid4()),
        username="inactiveuser",
        email="inactive@example.com",
        full_name="Inactive User",
        password_hash=hash_password("InactivePass123"),
        role="user",
        is_active=False,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_access_token(user: User) -> str:
    """Generate a JWT access token for the given user."""
    from datetime import timedelta

    token_data = {
        "sub": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }
    return create_access_token(data=token_data, expires_delta=timedelta(minutes=30))


@pytest.fixture(scope="function")
def auth_client(client: TestClient, test_user: User) -> TestClient:
    """Provide a test client with authentication cookies set for a regular user."""
    token = _make_access_token(test_user)
    client.cookies.set("access_token", token)
    return client


@pytest.fixture(scope="function")
def admin_client(client: TestClient, admin_user: User) -> TestClient:
    """Provide a test client with authentication cookies set for an admin user."""
    token = _make_access_token(admin_user)
    client.cookies.set("access_token", token)
    return client


@pytest.fixture(scope="function")
def sample_system_categories(db: Session) -> list[Category]:
    """Create and return sample system categories."""
    now = datetime.now(timezone.utc)
    categories_data = [
        {"name": "Salary", "type": "income", "color": "#22C55E", "icon": "💰"},
        {"name": "Freelance", "type": "income", "color": "#16A34A", "icon": "💻"},
        {"name": "Groceries", "type": "expense", "color": "#EF4444", "icon": "🛒"},
        {"name": "Rent", "type": "expense", "color": "#DC2626", "icon": "🏠"},
        {"name": "Utilities", "type": "expense", "color": "#F59E0B", "icon": "💡"},
        {"name": "Entertainment", "type": "expense", "color": "#8B5CF6", "icon": "🎬"},
        {"name": "Other", "type": "expense", "color": "#6B7280", "icon": None},
    ]

    categories = []
    for cat_data in categories_data:
        category = Category(
            id=str(uuid.uuid4()),
            name=cat_data["name"],
            type=cat_data["type"],
            color=cat_data["color"],
            icon=cat_data["icon"],
            is_system=True,
            user_id=None,
            created_at=now,
        )
        db.add(category)
        categories.append(category)

    db.commit()
    for cat in categories:
        db.refresh(cat)
    return categories


@pytest.fixture(scope="function")
def sample_custom_categories(db: Session, test_user: User) -> list[Category]:
    """Create and return sample custom categories for the test user."""
    now = datetime.now(timezone.utc)
    categories_data = [
        {"name": "Side Project", "type": "income", "color": "#10B981", "icon": "🚀"},
        {"name": "Coffee", "type": "expense", "color": "#92400E", "icon": "☕"},
    ]

    categories = []
    for cat_data in categories_data:
        category = Category(
            id=str(uuid.uuid4()),
            name=cat_data["name"],
            type=cat_data["type"],
            color=cat_data["color"],
            icon=cat_data["icon"],
            is_system=False,
            user_id=test_user.id,
            created_at=now,
        )
        db.add(category)
        categories.append(category)

    db.commit()
    for cat in categories:
        db.refresh(cat)
    return categories


@pytest.fixture(scope="function")
def sample_transactions(
    db: Session,
    test_user: User,
    sample_system_categories: list[Category],
) -> list[Transaction]:
    """Create and return sample transactions for the test user."""
    now = datetime.now(timezone.utc)

    salary_cat = next(c for c in sample_system_categories if c.name == "Salary")
    groceries_cat = next(c for c in sample_system_categories if c.name == "Groceries")
    rent_cat = next(c for c in sample_system_categories if c.name == "Rent")
    entertainment_cat = next(c for c in sample_system_categories if c.name == "Entertainment")

    transactions_data = [
        {
            "type": "income",
            "category": "Salary",
            "category_id": salary_cat.id,
            "amount": Decimal("5000.00"),
            "description": "Monthly salary",
            "transaction_date": date(2024, 1, 1),
        },
        {
            "type": "expense",
            "category": "Groceries",
            "category_id": groceries_cat.id,
            "amount": Decimal("150.50"),
            "description": "Weekly groceries",
            "transaction_date": date(2024, 1, 5),
        },
        {
            "type": "expense",
            "category": "Rent",
            "category_id": rent_cat.id,
            "amount": Decimal("1200.00"),
            "description": "January rent",
            "transaction_date": date(2024, 1, 1),
        },
        {
            "type": "expense",
            "category": "Entertainment",
            "category_id": entertainment_cat.id,
            "amount": Decimal("45.99"),
            "description": "Movie tickets",
            "transaction_date": date(2024, 1, 10),
        },
        {
            "type": "income",
            "category": "Salary",
            "category_id": salary_cat.id,
            "amount": Decimal("5000.00"),
            "description": "February salary",
            "transaction_date": date(2024, 2, 1),
        },
    ]

    transactions = []
    for txn_data in transactions_data:
        transaction = Transaction(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            type=txn_data["type"],
            category=txn_data["category"],
            category_id=txn_data["category_id"],
            amount=txn_data["amount"],
            description=txn_data["description"],
            transaction_date=txn_data["transaction_date"],
            created_at=now,
            updated_at=now,
        )
        db.add(transaction)
        transactions.append(transaction)

    db.commit()
    for txn in transactions:
        db.refresh(txn)
    return transactions


@pytest.fixture(scope="function")
def sample_budgets(
    db: Session,
    test_user: User,
    sample_system_categories: list[Category],
) -> list[Budget]:
    """Create and return sample budgets for the test user."""
    now = datetime.now(timezone.utc)

    groceries_cat = next(c for c in sample_system_categories if c.name == "Groceries")
    rent_cat = next(c for c in sample_system_categories if c.name == "Rent")
    entertainment_cat = next(c for c in sample_system_categories if c.name == "Entertainment")

    budgets_data = [
        {
            "category_id": groceries_cat.id,
            "month": "2024-01",
            "amount": 500.00,
        },
        {
            "category_id": rent_cat.id,
            "month": "2024-01",
            "amount": 1200.00,
        },
        {
            "category_id": entertainment_cat.id,
            "month": "2024-01",
            "amount": 100.00,
        },
    ]

    budgets = []
    for budget_data in budgets_data:
        budget = Budget(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            category_id=budget_data["category_id"],
            month=budget_data["month"],
            amount=budget_data["amount"],
            created_at=now,
        )
        db.add(budget)
        budgets.append(budget)

    db.commit()
    for b in budgets:
        db.refresh(b)
    return budgets


@pytest.fixture(scope="function")
def second_user(db: Session) -> User:
    """Create and return a second regular user for isolation tests."""
    now = datetime.now(timezone.utc)
    user = User(
        id=str(uuid.uuid4()),
        username="seconduser",
        email="second@example.com",
        full_name="Second User",
        password_hash=hash_password("SecondPass123"),
        role="user",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user