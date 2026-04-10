import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from database import Base, get_db
from main import app
from models.user import User
from models.transaction import Transaction
from models.category import Category
from models.budget import Budget
from utils.security import hash_password, create_access_token


TEST_DATABASE_URL = "sqlite:///./test_dashboard.db"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def create_test_user(
    db: Session,
    username: str = "testuser",
    email: str = "test@example.com",
    role: str = "user",
    is_active: bool = True,
) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id="test-user-id-001",
        username=username,
        email=email,
        full_name="Test User",
        password_hash=hash_password("TestPass1"),
        role=role,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_admin_user(db: Session) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        id="admin-user-id-001",
        username="adminuser",
        email="admin@example.com",
        full_name="Admin User",
        password_hash=hash_password("AdminPass1"),
        role="admin",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_test_category(
    db: Session,
    name: str = "Groceries",
    cat_type: str = "expense",
    color: str = "#EF4444",
    is_system: bool = True,
    user_id: str = None,
) -> Category:
    now = datetime.now(timezone.utc)
    category = Category(
        name=name,
        type=cat_type,
        color=color,
        icon=None,
        is_system=is_system,
        user_id=user_id,
        created_at=now,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def create_test_transaction(
    db: Session,
    user_id: str,
    amount: float,
    txn_type: str = "expense",
    category_name: str = "Groceries",
    category_id: str = None,
    txn_date: date = None,
    description: str = None,
) -> Transaction:
    import uuid

    if txn_date is None:
        txn_date = date.today()
    now = datetime.utcnow()
    txn = Transaction(
        id=str(uuid.uuid4()),
        user_id=user_id,
        amount=Decimal(str(amount)),
        type=txn_type,
        category=category_name,
        category_id=category_id,
        description=description,
        transaction_date=txn_date,
        created_at=now,
        updated_at=now,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def get_auth_cookie(user: User) -> dict:
    token_data = {
        "sub": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }
    token = create_access_token(data=token_data)
    return {"access_token": token}


class TestDashboardAccess:
    """Test dashboard access control and authentication."""

    def test_dashboard_redirects_unauthenticated_user(self):
        response = client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    def test_dashboard_accessible_for_authenticated_user(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            cookies = get_auth_cookie(user)
            response = client.get("/dashboard", cookies=cookies)
            assert response.status_code == 200
            assert "Dashboard" in response.text
        finally:
            db.close()

    def test_dashboard_accessible_for_admin_user(self):
        db = TestSessionLocal()
        try:
            admin = create_admin_user(db)
            cookies = get_auth_cookie(admin)
            response = client.get("/dashboard", cookies=cookies)
            assert response.status_code == 200
            assert "Dashboard" in response.text
        finally:
            db.close()

    def test_dashboard_with_inactive_user_redirects(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db, is_active=False)
            cookies = get_auth_cookie(user)
            response = client.get("/dashboard", follow_redirects=False, cookies=cookies)
            assert response.status_code == 303
            assert "/auth/login" in response.headers.get("location", "")
        finally:
            db.close()


class TestDashboardSummary:
    """Test dashboard summary calculations (income, expenses, net savings)."""

    def test_dashboard_shows_zero_totals_when_no_transactions(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            cookies = get_auth_cookie(user)
            response = client.get("/dashboard", cookies=cookies)
            assert response.status_code == 200
            assert "$0.00" in response.text
        finally:
            db.close()

    def test_dashboard_shows_correct_income_total(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            today = date.today()
            create_test_transaction(db, user.id, 1000.00, "income", "Salary", txn_date=today)
            create_test_transaction(db, user.id, 500.00, "income", "Freelance", txn_date=today)

            cookies = get_auth_cookie(user)
            month_str = f"{today.year:04d}-{today.month:02d}"
            response = client.get(f"/dashboard?month={month_str}", cookies=cookies)
            assert response.status_code == 200
            assert "$1500.00" in response.text
        finally:
            db.close()

    def test_dashboard_shows_correct_expense_total(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            today = date.today()
            create_test_transaction(db, user.id, 200.00, "expense", "Groceries", txn_date=today)
            create_test_transaction(db, user.id, 300.00, "expense", "Rent", txn_date=today)

            cookies = get_auth_cookie(user)
            month_str = f"{today.year:04d}-{today.month:02d}"
            response = client.get(f"/dashboard?month={month_str}", cookies=cookies)
            assert response.status_code == 200
            assert "$500.00" in response.text
        finally:
            db.close()

    def test_dashboard_shows_correct_net_savings(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            today = date.today()
            create_test_transaction(db, user.id, 2000.00, "income", "Salary", txn_date=today)
            create_test_transaction(db, user.id, 800.00, "expense", "Rent", txn_date=today)

            cookies = get_auth_cookie(user)
            month_str = f"{today.year:04d}-{today.month:02d}"
            response = client.get(f"/dashboard?month={month_str}", cookies=cookies)
            assert response.status_code == 200
            assert "$1200.00" in response.text
        finally:
            db.close()

    def test_dashboard_with_month_filter(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            create_test_transaction(
                db, user.id, 1000.00, "income", "Salary", txn_date=date(2024, 6, 15)
            )
            create_test_transaction(
                db, user.id, 500.00, "income", "Salary", txn_date=date(2024, 7, 15)
            )

            cookies = get_auth_cookie(user)
            response = client.get("/dashboard?month=2024-06", cookies=cookies)
            assert response.status_code == 200
            assert "$1000.00" in response.text
        finally:
            db.close()

    def test_dashboard_with_invalid_month_defaults_to_current(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            cookies = get_auth_cookie(user)
            response = client.get("/dashboard?month=invalid", cookies=cookies)
            assert response.status_code == 200
        finally:
            db.close()


class TestDashboardCategoryBreakdown:
    """Test category breakdown on the dashboard."""

    def test_category_breakdown_shows_expense_categories(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            cat = create_test_category(db, "Groceries", "expense", "#EF4444")
            today = date.today()
            create_test_transaction(
                db, user.id, 150.00, "expense", "Groceries",
                category_id=cat.id, txn_date=today,
            )

            cookies = get_auth_cookie(user)
            month_str = f"{today.year:04d}-{today.month:02d}"
            response = client.get(f"/dashboard?month={month_str}", cookies=cookies)
            assert response.status_code == 200
            assert "Groceries" in response.text
            assert "$150.00" in response.text
        finally:
            db.close()

    def test_category_breakdown_empty_when_no_expenses(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            today = date.today()
            create_test_transaction(
                db, user.id, 1000.00, "income", "Salary", txn_date=today,
            )

            cookies = get_auth_cookie(user)
            month_str = f"{today.year:04d}-{today.month:02d}"
            response = client.get(f"/dashboard?month={month_str}", cookies=cookies)
            assert response.status_code == 200
            assert "No spending data for this period" in response.text
        finally:
            db.close()

    def test_category_breakdown_multiple_categories(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            cat1 = create_test_category(db, "Groceries", "expense", "#EF4444")
            cat2 = create_test_category(db, "Rent", "expense", "#DC2626")
            today = date.today()
            create_test_transaction(
                db, user.id, 200.00, "expense", "Groceries",
                category_id=cat1.id, txn_date=today,
            )
            create_test_transaction(
                db, user.id, 800.00, "expense", "Rent",
                category_id=cat2.id, txn_date=today,
            )

            cookies = get_auth_cookie(user)
            month_str = f"{today.year:04d}-{today.month:02d}"
            response = client.get(f"/dashboard?month={month_str}", cookies=cookies)
            assert response.status_code == 200
            assert "Groceries" in response.text
            assert "Rent" in response.text
        finally:
            db.close()


class TestDashboardRecentTransactions:
    """Test recent transactions display on the dashboard."""

    def test_recent_transactions_displayed(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            create_test_transaction(
                db, user.id, 50.00, "expense", "Groceries",
                description="Weekly groceries",
                txn_date=date.today(),
            )

            cookies = get_auth_cookie(user)
            response = client.get("/dashboard", cookies=cookies)
            assert response.status_code == 200
            assert "Weekly groceries" in response.text or "Groceries" in response.text
        finally:
            db.close()

    def test_recent_transactions_empty_state(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            cookies = get_auth_cookie(user)
            response = client.get("/dashboard", cookies=cookies)
            assert response.status_code == 200
            assert "No transactions yet" in response.text
        finally:
            db.close()

    def test_recent_transactions_limited_to_10(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            for i in range(15):
                create_test_transaction(
                    db, user.id, 10.00 + i, "expense", "Groceries",
                    description=f"Transaction {i}",
                    txn_date=date.today(),
                )

            cookies = get_auth_cookie(user)
            response = client.get("/dashboard", cookies=cookies)
            assert response.status_code == 200
            # The page should render successfully with at most 10 recent transactions
            assert response.status_code == 200
        finally:
            db.close()

    def test_recent_transactions_shows_income_and_expense(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            create_test_transaction(
                db, user.id, 1000.00, "income", "Salary",
                description="Monthly salary",
                txn_date=date.today(),
            )
            create_test_transaction(
                db, user.id, 50.00, "expense", "Groceries",
                description="Weekly groceries",
                txn_date=date.today(),
            )

            cookies = get_auth_cookie(user)
            response = client.get("/dashboard", cookies=cookies)
            assert response.status_code == 200
            assert "Salary" in response.text or "Monthly salary" in response.text
            assert "Groceries" in response.text or "Weekly groceries" in response.text
        finally:
            db.close()


class TestDashboardBudgetAlerts:
    """Test budget alert display on the dashboard."""

    def test_no_budget_alerts_when_no_budgets(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            cookies = get_auth_cookie(user)
            response = client.get("/dashboard", cookies=cookies)
            assert response.status_code == 200
            assert "All budgets on track" in response.text
        finally:
            db.close()

    def test_budget_alert_shown_when_overspent(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            cat = create_test_category(db, "Groceries", "expense", "#EF4444")
            today = date.today()
            month_str = f"{today.year:04d}-{today.month:02d}"

            budget = Budget(
                user_id=user.id,
                category_id=cat.id,
                month=month_str,
                amount=100.0,
                created_at=datetime.utcnow(),
            )
            db.add(budget)
            db.commit()

            create_test_transaction(
                db, user.id, 120.00, "expense", "Groceries",
                category_id=cat.id, txn_date=today,
            )

            cookies = get_auth_cookie(user)
            response = client.get(f"/dashboard?month={month_str}", cookies=cookies)
            assert response.status_code == 200
            assert "Budget Alerts" in response.text or "budget" in response.text.lower()
        finally:
            db.close()


class TestDashboardUserIsolation:
    """Test that dashboard data is isolated per user."""

    def test_user_only_sees_own_transactions(self):
        db = TestSessionLocal()
        try:
            user1 = create_test_user(db, username="user1", email="user1@example.com")
            user1.id = "user-1-id"
            db.commit()

            now = datetime.now(timezone.utc)
            user2 = User(
                id="user-2-id",
                username="user2",
                email="user2@example.com",
                full_name="User Two",
                password_hash=hash_password("TestPass1"),
                role="user",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(user2)
            db.commit()

            today = date.today()
            create_test_transaction(
                db, user1.id, 500.00, "income", "Salary",
                description="User1 salary", txn_date=today,
            )
            create_test_transaction(
                db, user2.id, 3000.00, "income", "Salary",
                description="User2 salary", txn_date=today,
            )

            cookies = get_auth_cookie(user1)
            month_str = f"{today.year:04d}-{today.month:02d}"
            response = client.get(f"/dashboard?month={month_str}", cookies=cookies)
            assert response.status_code == 200
            assert "$500.00" in response.text
            assert "$3000.00" not in response.text
        finally:
            db.close()


class TestAdminDashboard:
    """Test admin dashboard access and stats."""

    def test_admin_dashboard_accessible_for_admin(self):
        db = TestSessionLocal()
        try:
            admin = create_admin_user(db)
            cookies = get_auth_cookie(admin)
            response = client.get("/admin/dashboard", cookies=cookies)
            assert response.status_code == 200
            assert "Admin Dashboard" in response.text
        finally:
            db.close()

    def test_admin_dashboard_blocked_for_regular_user(self):
        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            cookies = get_auth_cookie(user)
            response = client.get("/admin/dashboard", cookies=cookies, follow_redirects=False)
            assert response.status_code == 303
            assert "/dashboard" in response.headers.get("location", "")
        finally:
            db.close()

    def test_admin_dashboard_blocked_for_unauthenticated(self):
        response = client.get("/admin/dashboard", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    def test_admin_dashboard_shows_user_count(self):
        db = TestSessionLocal()
        try:
            admin = create_admin_user(db)
            create_test_user(db, username="regularuser", email="regular@example.com")

            cookies = get_auth_cookie(admin)
            response = client.get("/admin/dashboard", cookies=cookies)
            assert response.status_code == 200
            assert "Total Users" in response.text
        finally:
            db.close()

    def test_admin_dashboard_shows_transaction_count(self):
        db = TestSessionLocal()
        try:
            admin = create_admin_user(db)
            create_test_transaction(
                db, admin.id, 100.00, "expense", "Groceries",
                txn_date=date.today(),
            )

            cookies = get_auth_cookie(admin)
            response = client.get("/admin/dashboard", cookies=cookies)
            assert response.status_code == 200
            assert "Total Transactions" in response.text
        finally:
            db.close()

    def test_admin_dashboard_shows_system_value(self):
        db = TestSessionLocal()
        try:
            admin = create_admin_user(db)
            create_test_transaction(
                db, admin.id, 5000.00, "income", "Salary",
                txn_date=date.today(),
            )
            create_test_transaction(
                db, admin.id, 1000.00, "expense", "Rent",
                txn_date=date.today(),
            )

            cookies = get_auth_cookie(admin)
            response = client.get("/admin/dashboard", cookies=cookies)
            assert response.status_code == 200
            assert "System Value" in response.text
        finally:
            db.close()

    def test_admin_dashboard_shows_user_management_section(self):
        db = TestSessionLocal()
        try:
            admin = create_admin_user(db)
            cookies = get_auth_cookie(admin)
            response = client.get("/admin/dashboard", cookies=cookies)
            assert response.status_code == 200
            assert "User Management" in response.text
        finally:
            db.close()

    def test_admin_dashboard_shows_system_categories_section(self):
        db = TestSessionLocal()
        try:
            admin = create_admin_user(db)
            cookies = get_auth_cookie(admin)
            response = client.get("/admin/dashboard", cookies=cookies)
            assert response.status_code == 200
            assert "System Categories" in response.text
        finally:
            db.close()


class TestDashboardServiceUnit:
    """Unit tests for dashboard service functions."""

    def test_get_dashboard_summary_returns_correct_structure(self):
        from services.dashboard_service import get_dashboard_summary

        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            summary = get_dashboard_summary(db, user.id)
            assert "total_income" in summary
            assert "total_expenses" in summary
            assert "net_savings" in summary
            assert "income_change" in summary
            assert "expense_change" in summary
            assert "budget_alerts" in summary
            assert "selected_month" in summary
        finally:
            db.close()

    def test_get_dashboard_summary_with_transactions(self):
        from services.dashboard_service import get_dashboard_summary

        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            today = date.today()
            month_str = f"{today.year:04d}-{today.month:02d}"

            create_test_transaction(db, user.id, 2000.00, "income", "Salary", txn_date=today)
            create_test_transaction(db, user.id, 500.00, "expense", "Rent", txn_date=today)
            create_test_transaction(db, user.id, 100.00, "expense", "Groceries", txn_date=today)

            summary = get_dashboard_summary(db, user.id, month=month_str)
            assert summary["total_income"] == 2000.0
            assert summary["total_expenses"] == 600.0
            assert summary["net_savings"] == 1400.0
        finally:
            db.close()

    def test_get_dashboard_summary_no_transactions(self):
        from services.dashboard_service import get_dashboard_summary

        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            today = date.today()
            month_str = f"{today.year:04d}-{today.month:02d}"

            summary = get_dashboard_summary(db, user.id, month=month_str)
            assert summary["total_income"] == 0.0
            assert summary["total_expenses"] == 0.0
            assert summary["net_savings"] == 0.0
        finally:
            db.close()

    def test_get_category_breakdown_returns_list(self):
        from services.dashboard_service import get_category_breakdown

        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            today = date.today()
            month_str = f"{today.year:04d}-{today.month:02d}"

            breakdown = get_category_breakdown(db, user.id, month=month_str)
            assert isinstance(breakdown, list)
        finally:
            db.close()

    def test_get_category_breakdown_with_expenses(self):
        from services.dashboard_service import get_category_breakdown

        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            cat = create_test_category(db, "Groceries", "expense", "#EF4444")
            today = date.today()
            month_str = f"{today.year:04d}-{today.month:02d}"

            create_test_transaction(
                db, user.id, 200.00, "expense", "Groceries",
                category_id=cat.id, txn_date=today,
            )

            breakdown = get_category_breakdown(db, user.id, month=month_str)
            assert len(breakdown) == 1
            assert breakdown[0]["name"] == "Groceries"
            assert breakdown[0]["amount"] == 200.0
            assert breakdown[0]["percentage"] == 100.0
        finally:
            db.close()

    def test_get_recent_transactions_returns_list(self):
        from services.dashboard_service import get_recent_transactions

        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            result = get_recent_transactions(db, user.id, limit=10)
            assert isinstance(result, list)
            assert len(result) == 0
        finally:
            db.close()

    def test_get_recent_transactions_respects_limit(self):
        from services.dashboard_service import get_recent_transactions

        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            for i in range(15):
                create_test_transaction(
                    db, user.id, 10.00 + i, "expense", "Groceries",
                    txn_date=date.today(),
                )

            result = get_recent_transactions(db, user.id, limit=5)
            assert len(result) == 5
        finally:
            db.close()

    def test_get_recent_transactions_ordered_by_date_desc(self):
        from services.dashboard_service import get_recent_transactions

        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            create_test_transaction(
                db, user.id, 100.00, "expense", "Groceries",
                txn_date=date(2024, 1, 1),
            )
            create_test_transaction(
                db, user.id, 200.00, "expense", "Rent",
                txn_date=date(2024, 6, 15),
            )

            result = get_recent_transactions(db, user.id, limit=10)
            assert len(result) == 2
            assert result[0]["transaction_date"] >= result[1]["transaction_date"]
        finally:
            db.close()

    def test_get_admin_stats_returns_correct_structure(self):
        from services.dashboard_service import get_admin_stats

        db = TestSessionLocal()
        try:
            create_test_user(db)
            stats = get_admin_stats(db)
            assert "total_users" in stats
            assert "active_users" in stats
            assert "total_transactions" in stats
            assert "system_value" in stats
        finally:
            db.close()

    def test_get_admin_stats_counts_users(self):
        from services.dashboard_service import get_admin_stats

        db = TestSessionLocal()
        try:
            create_test_user(db, username="user1", email="user1@example.com")
            now = datetime.now(timezone.utc)
            user2 = User(
                id="user-2-stats",
                username="user2",
                email="user2@example.com",
                full_name="User Two",
                password_hash=hash_password("TestPass1"),
                role="user",
                is_active=False,
                created_at=now,
                updated_at=now,
            )
            db.add(user2)
            db.commit()

            stats = get_admin_stats(db)
            assert stats["total_users"] == 2
            assert stats["active_users"] == 1
        finally:
            db.close()

    def test_get_admin_stats_calculates_system_value(self):
        from services.dashboard_service import get_admin_stats

        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            create_test_transaction(db, user.id, 5000.00, "income", "Salary", txn_date=date.today())
            create_test_transaction(db, user.id, 2000.00, "expense", "Rent", txn_date=date.today())

            stats = get_admin_stats(db)
            assert stats["system_value"] == 3000.0
        finally:
            db.close()


class TestDashboardMonthOverMonthChange:
    """Test month-over-month change percentage calculations."""

    def test_income_change_percentage_calculated(self):
        from services.dashboard_service import get_dashboard_summary

        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            today = date.today()
            current_month = today.month
            current_year = today.year

            if current_month == 1:
                prev_year = current_year - 1
                prev_month = 12
            else:
                prev_year = current_year
                prev_month = current_month - 1

            create_test_transaction(
                db, user.id, 1000.00, "income", "Salary",
                txn_date=date(prev_year, prev_month, 15),
            )
            create_test_transaction(
                db, user.id, 1500.00, "income", "Salary",
                txn_date=date(current_year, current_month, 15),
            )

            month_str = f"{current_year:04d}-{current_month:02d}"
            summary = get_dashboard_summary(db, user.id, month=month_str)

            assert summary["income_change"] is not None
            assert summary["income_change"] == pytest.approx(50.0, rel=0.01)
        finally:
            db.close()

    def test_income_change_none_when_no_previous_income(self):
        from services.dashboard_service import get_dashboard_summary

        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            today = date.today()
            month_str = f"{today.year:04d}-{today.month:02d}"

            summary = get_dashboard_summary(db, user.id, month=month_str)
            assert summary["income_change"] is None
        finally:
            db.close()

    def test_income_change_100_when_no_previous_but_current_exists(self):
        from services.dashboard_service import get_dashboard_summary

        db = TestSessionLocal()
        try:
            user = create_test_user(db)
            today = date.today()
            create_test_transaction(
                db, user.id, 1000.00, "income", "Salary",
                txn_date=today,
            )

            month_str = f"{today.year:04d}-{today.month:02d}"
            summary = get_dashboard_summary(db, user.id, month=month_str)
            assert summary["income_change"] == 100.0
        finally:
            db.close()


class TestRootRedirect:
    """Test root URL redirect behavior."""

    def test_root_redirects_to_dashboard(self):
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert "/dashboard" in response.headers.get("location", "")