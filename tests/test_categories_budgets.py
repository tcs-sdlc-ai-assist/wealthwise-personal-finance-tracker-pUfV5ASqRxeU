import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker, Session

from database import Base
from models.user import User
from models.category import Category
from models.transaction import Transaction
from models.budget import Budget
from utils.security import hash_password
from services.category_service import (
    get_categories_for_user,
    get_system_categories,
    get_custom_categories,
    get_category_by_id,
    get_category_by_name_and_user,
    get_category_transaction_count,
    create_category,
    update_category,
    delete_category,
    create_system_category,
    update_system_category,
    delete_system_category,
    get_categories_with_transaction_counts,
    get_system_categories_with_transaction_counts,
)
from services.budget_service import (
    get_budgets_for_month,
    set_budget,
    check_overspend,
    bulk_save_budgets,
    delete_budget,
    get_budget_by_id,
    get_budget_summary,
)


@pytest.fixture(scope="function")
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db(db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def test_user(db: Session) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        password_hash=hash_password("TestPass1"),
        role="user",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def second_user(db: Session) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        username="seconduser",
        email="second@example.com",
        full_name="Second User",
        password_hash=hash_password("TestPass1"),
        role="user",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def system_categories(db: Session) -> list[Category]:
    now = datetime.now(timezone.utc)
    categories = []
    for cat_data in [
        {"name": "Salary", "type": "income", "color": "#22C55E", "icon": "💰"},
        {"name": "Groceries", "type": "expense", "color": "#EF4444", "icon": "🛒"},
        {"name": "Rent", "type": "expense", "color": "#B91C1C", "icon": "🏠"},
        {"name": "Other", "type": "expense", "color": "#6B7280", "icon": None},
    ]:
        cat = Category(
            name=cat_data["name"],
            type=cat_data["type"],
            color=cat_data["color"],
            icon=cat_data["icon"],
            is_system=True,
            user_id=None,
            created_at=now,
        )
        db.add(cat)
        categories.append(cat)
    db.commit()
    for cat in categories:
        db.refresh(cat)
    return categories


@pytest.fixture
def custom_category(db: Session, test_user: User) -> Category:
    now = datetime.now(timezone.utc)
    cat = Category(
        name="My Custom",
        type="expense",
        color="#FF5733",
        icon="🎯",
        is_system=False,
        user_id=test_user.id,
        created_at=now,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


# ============================================================
# Category Service Tests
# ============================================================


class TestGetCategoriesForUser:
    def test_returns_system_and_custom_categories(
        self, db: Session, test_user: User, system_categories, custom_category
    ):
        categories = get_categories_for_user(db, test_user.id)
        names = [c.name for c in categories]
        assert "Salary" in names
        assert "Groceries" in names
        assert "My Custom" in names

    def test_does_not_return_other_users_custom_categories(
        self, db: Session, test_user: User, second_user: User, system_categories
    ):
        now = datetime.now(timezone.utc)
        other_cat = Category(
            name="Other User Cat",
            type="expense",
            color="#123456",
            icon=None,
            is_system=False,
            user_id=second_user.id,
            created_at=now,
        )
        db.add(other_cat)
        db.commit()

        categories = get_categories_for_user(db, test_user.id)
        names = [c.name for c in categories]
        assert "Other User Cat" not in names

    def test_returns_empty_when_no_categories(self, db: Session, test_user: User):
        categories = get_categories_for_user(db, test_user.id)
        assert categories == []


class TestGetSystemCategories:
    def test_returns_only_system_categories(
        self, db: Session, system_categories, custom_category
    ):
        cats = get_system_categories(db)
        assert all(c.is_system for c in cats)
        names = [c.name for c in cats]
        assert "My Custom" not in names

    def test_returns_empty_when_no_system_categories(self, db: Session):
        cats = get_system_categories(db)
        assert cats == []


class TestGetCustomCategories:
    def test_returns_only_user_custom_categories(
        self, db: Session, test_user: User, system_categories, custom_category
    ):
        cats = get_custom_categories(db, test_user.id)
        assert len(cats) == 1
        assert cats[0].name == "My Custom"
        assert cats[0].is_system is False

    def test_returns_empty_for_user_with_no_custom(
        self, db: Session, second_user: User, system_categories
    ):
        cats = get_custom_categories(db, second_user.id)
        assert cats == []


class TestCreateCategory:
    def test_create_custom_category_success(self, db: Session, test_user: User):
        cat = create_category(
            db=db,
            user_id=test_user.id,
            name="Travel",
            description="Travel expenses",
            color="#0000FF",
            icon="✈️",
            is_active=True,
        )
        assert cat.name == "Travel"
        assert cat.is_system is False
        assert cat.user_id == test_user.id
        assert cat.color == "#0000FF"

    def test_create_duplicate_category_raises_value_error(
        self, db: Session, test_user: User, custom_category
    ):
        with pytest.raises(ValueError, match="already exists"):
            create_category(
                db=db,
                user_id=test_user.id,
                name="My Custom",
            )

    def test_create_category_strips_whitespace(self, db: Session, test_user: User):
        cat = create_category(
            db=db,
            user_id=test_user.id,
            name="  Hobbies  ",
        )
        assert cat.name == "Hobbies"


class TestUpdateCategory:
    def test_update_custom_category_name(
        self, db: Session, test_user: User, custom_category
    ):
        updated = update_category(
            db=db,
            category_id=custom_category.id,
            user_id=test_user.id,
            name="Updated Name",
        )
        assert updated is not None
        assert updated.name == "Updated Name"

    def test_update_custom_category_color(
        self, db: Session, test_user: User, custom_category
    ):
        updated = update_category(
            db=db,
            category_id=custom_category.id,
            user_id=test_user.id,
            color="#AABBCC",
        )
        assert updated is not None
        assert updated.color == "#AABBCC"

    def test_update_nonexistent_category_returns_none(
        self, db: Session, test_user: User
    ):
        result = update_category(
            db=db,
            category_id="nonexistent-id",
            user_id=test_user.id,
            name="Whatever",
        )
        assert result is None

    def test_update_system_category_raises_value_error(
        self, db: Session, test_user: User, system_categories
    ):
        system_cat = system_categories[0]
        with pytest.raises(ValueError, match="System categories cannot be updated"):
            update_category(
                db=db,
                category_id=system_cat.id,
                user_id=test_user.id,
                name="Hacked Name",
            )

    def test_update_other_users_category_raises_permission_error(
        self, db: Session, test_user: User, second_user: User, custom_category
    ):
        with pytest.raises(PermissionError, match="do not have permission"):
            update_category(
                db=db,
                category_id=custom_category.id,
                user_id=second_user.id,
                name="Stolen",
            )

    def test_update_to_duplicate_name_raises_value_error(
        self, db: Session, test_user: User, custom_category
    ):
        create_category(db=db, user_id=test_user.id, name="Another Cat")
        with pytest.raises(ValueError, match="already exists"):
            update_category(
                db=db,
                category_id=custom_category.id,
                user_id=test_user.id,
                name="Another Cat",
            )


class TestDeleteCategory:
    def test_delete_custom_category_success(
        self, db: Session, test_user: User, custom_category, system_categories
    ):
        result = delete_category(
            db=db,
            category_id=custom_category.id,
            user_id=test_user.id,
        )
        assert result is True
        assert get_category_by_id(db, custom_category.id) is None

    def test_delete_category_reassigns_transactions_to_other(
        self, db: Session, test_user: User, custom_category, system_categories
    ):
        txn = Transaction(
            user_id=test_user.id,
            category_id=custom_category.id,
            type="expense",
            amount=Decimal("50.00"),
            category=custom_category.name,
            description="Test txn",
            transaction_date=date.today(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(txn)
        db.commit()
        db.refresh(txn)
        txn_id = txn.id

        delete_category(
            db=db,
            category_id=custom_category.id,
            user_id=test_user.id,
        )

        updated_txn = db.execute(
            select(Transaction).where(Transaction.id == txn_id)
        ).scalars().first()
        assert updated_txn is not None
        assert updated_txn.category == "Other"

    def test_delete_nonexistent_category_returns_false(
        self, db: Session, test_user: User
    ):
        result = delete_category(
            db=db,
            category_id="nonexistent-id",
            user_id=test_user.id,
        )
        assert result is False

    def test_delete_system_category_raises_value_error(
        self, db: Session, test_user: User, system_categories
    ):
        with pytest.raises(ValueError, match="System categories cannot be deleted"):
            delete_category(
                db=db,
                category_id=system_categories[0].id,
                user_id=test_user.id,
            )

    def test_delete_other_users_category_raises_permission_error(
        self, db: Session, second_user: User, custom_category
    ):
        with pytest.raises(PermissionError, match="do not have permission"):
            delete_category(
                db=db,
                category_id=custom_category.id,
                user_id=second_user.id,
            )


class TestGetCategoryTransactionCount:
    def test_count_with_transactions(
        self, db: Session, test_user: User, custom_category
    ):
        for i in range(3):
            txn = Transaction(
                user_id=test_user.id,
                category_id=custom_category.id,
                type="expense",
                amount=Decimal("10.00"),
                category=custom_category.name,
                transaction_date=date.today(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(txn)
        db.commit()

        count = get_category_transaction_count(db, custom_category.id)
        assert count == 3

    def test_count_with_no_transactions(self, db: Session, custom_category):
        count = get_category_transaction_count(db, custom_category.id)
        assert count == 0


class TestSystemCategoryAdmin:
    def test_create_system_category(self, db: Session):
        cat = create_system_category(
            db=db,
            name="Insurance",
            description="Insurance payments",
            color="#FF00FF",
            icon="🛡️",
        )
        assert cat.name == "Insurance"
        assert cat.is_system is True
        assert cat.user_id is None

    def test_create_duplicate_system_category_raises_error(
        self, db: Session, system_categories
    ):
        with pytest.raises(ValueError, match="already exists"):
            create_system_category(db=db, name="Salary")

    def test_update_system_category_admin(self, db: Session, system_categories):
        cat = system_categories[0]
        updated = update_system_category(
            db=db,
            category_id=cat.id,
            name="Updated Salary",
            color="#00FF00",
        )
        assert updated is not None
        assert updated.name == "Updated Salary"
        assert updated.color == "#00FF00"

    def test_update_non_system_category_raises_error(
        self, db: Session, custom_category
    ):
        with pytest.raises(ValueError, match="not a system category"):
            update_system_category(
                db=db,
                category_id=custom_category.id,
                name="Hacked",
            )

    def test_delete_system_category_admin(self, db: Session, system_categories):
        groceries = next(c for c in system_categories if c.name == "Groceries")
        result = delete_system_category(db=db, category_id=groceries.id)
        assert result is True
        assert get_category_by_id(db, groceries.id) is None

    def test_delete_other_system_category_cannot_delete(
        self, db: Session, system_categories
    ):
        other_cat = next(c for c in system_categories if c.name == "Other")
        with pytest.raises(ValueError, match="Cannot delete the 'Other'"):
            delete_system_category(db=db, category_id=other_cat.id)


class TestGetCategoriesWithTransactionCounts:
    def test_returns_counts(
        self, db: Session, test_user: User, system_categories, custom_category
    ):
        txn = Transaction(
            user_id=test_user.id,
            category_id=custom_category.id,
            type="expense",
            amount=Decimal("25.00"),
            category=custom_category.name,
            transaction_date=date.today(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(txn)
        db.commit()

        result = get_categories_with_transaction_counts(db, test_user.id)
        custom_entry = next(
            (r for r in result if r["name"] == "My Custom"), None
        )
        assert custom_entry is not None
        assert custom_entry["transaction_count"] == 1

    def test_system_categories_with_counts(self, db: Session, system_categories):
        result = get_system_categories_with_transaction_counts(db)
        assert len(result) == len(system_categories)
        for entry in result:
            assert entry["is_system"] is True
            assert entry["transaction_count"] == 0


# ============================================================
# Budget Service Tests
# ============================================================


class TestSetBudget:
    def test_create_new_budget(
        self, db: Session, test_user: User, system_categories
    ):
        result = set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Groceries",
            amount=500.0,
            month="2024-06",
        )
        assert result["category"] == "Groceries"
        assert result["amount"] == 500.0
        assert result["month"] == "2024-06"

    def test_update_existing_budget(
        self, db: Session, test_user: User, system_categories
    ):
        set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Groceries",
            amount=500.0,
            month="2024-06",
        )
        result = set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Groceries",
            amount=750.0,
            month="2024-06",
        )
        assert result["amount"] == 750.0

    def test_create_budget_with_new_category(self, db: Session, test_user: User):
        result = set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Brand New Category",
            amount=200.0,
            month="2024-07",
        )
        assert result["category"] == "Brand New Category"
        assert result["amount"] == 200.0

        cat = db.execute(
            select(Category).where(
                Category.name == "Brand New Category",
                Category.user_id == test_user.id,
            )
        ).scalars().first()
        assert cat is not None
        assert cat.is_system is False


class TestGetBudgetsForMonth:
    def test_returns_budgets_with_spending(
        self, db: Session, test_user: User, system_categories
    ):
        groceries_cat = next(c for c in system_categories if c.name == "Groceries")

        set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Groceries",
            amount=500.0,
            month="2024-06",
        )

        txn = Transaction(
            user_id=test_user.id,
            category_id=groceries_cat.id,
            type="expense",
            amount=Decimal("150.00"),
            category="Groceries",
            transaction_date=date(2024, 6, 15),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(txn)
        db.commit()

        budgets = get_budgets_for_month(db, test_user.id, "2024-06")
        assert len(budgets) == 1
        assert budgets[0]["category"] == "Groceries"
        assert budgets[0]["amount"] == 500.0
        assert budgets[0]["spent"] == 150.0
        assert budgets[0]["remaining"] == 350.0

    def test_returns_empty_for_no_budgets(self, db: Session, test_user: User):
        budgets = get_budgets_for_month(db, test_user.id, "2024-01")
        assert budgets == []

    def test_returns_empty_for_invalid_month(self, db: Session, test_user: User):
        budgets = get_budgets_for_month(db, test_user.id, "bad")
        assert budgets == []


class TestGetBudgetById:
    def test_returns_budget_when_exists(
        self, db: Session, test_user: User, system_categories
    ):
        created = set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Rent",
            amount=1200.0,
            month="2024-06",
        )
        budget = get_budget_by_id(db, test_user.id, created["id"])
        assert budget is not None
        assert budget["category"] == "Rent"
        assert budget["amount"] == 1200.0

    def test_returns_none_for_nonexistent(self, db: Session, test_user: User):
        budget = get_budget_by_id(db, test_user.id, "nonexistent-id")
        assert budget is None

    def test_returns_none_for_other_users_budget(
        self, db: Session, test_user: User, second_user: User, system_categories
    ):
        created = set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Rent",
            amount=1200.0,
            month="2024-06",
        )
        budget = get_budget_by_id(db, second_user.id, created["id"])
        assert budget is None


class TestDeleteBudget:
    def test_delete_existing_budget(
        self, db: Session, test_user: User, system_categories
    ):
        created = set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Groceries",
            amount=500.0,
            month="2024-06",
        )
        result = delete_budget(db, test_user.id, created["id"])
        assert result is True

        budget = get_budget_by_id(db, test_user.id, created["id"])
        assert budget is None

    def test_delete_nonexistent_budget_returns_false(
        self, db: Session, test_user: User
    ):
        result = delete_budget(db, test_user.id, "nonexistent-id")
        assert result is False

    def test_delete_other_users_budget_returns_false(
        self, db: Session, test_user: User, second_user: User, system_categories
    ):
        created = set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Groceries",
            amount=500.0,
            month="2024-06",
        )
        result = delete_budget(db, second_user.id, created["id"])
        assert result is False


class TestBulkSaveBudgets:
    def test_bulk_update_budgets(
        self, db: Session, test_user: User, system_categories
    ):
        b1 = set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Groceries",
            amount=500.0,
            month="2024-06",
        )
        b2 = set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Rent",
            amount=1200.0,
            month="2024-06",
        )

        updated_count = bulk_save_budgets(
            db=db,
            user_id=test_user.id,
            budget_ids=[b1["id"], b2["id"]],
            amounts=[600.0, 1300.0],
        )
        assert updated_count == 2

        updated_b1 = get_budget_by_id(db, test_user.id, b1["id"])
        assert updated_b1["amount"] == 600.0

        updated_b2 = get_budget_by_id(db, test_user.id, b2["id"])
        assert updated_b2["amount"] == 1300.0

    def test_bulk_save_mismatched_lengths_raises_error(
        self, db: Session, test_user: User
    ):
        with pytest.raises(ValueError, match="same length"):
            bulk_save_budgets(
                db=db,
                user_id=test_user.id,
                budget_ids=["id1", "id2"],
                amounts=[100.0],
            )

    def test_bulk_save_skips_zero_or_negative_amounts(
        self, db: Session, test_user: User, system_categories
    ):
        b1 = set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Groceries",
            amount=500.0,
            month="2024-06",
        )
        updated_count = bulk_save_budgets(
            db=db,
            user_id=test_user.id,
            budget_ids=[b1["id"]],
            amounts=[0.0],
        )
        assert updated_count == 0

        budget = get_budget_by_id(db, test_user.id, b1["id"])
        assert budget["amount"] == 500.0


class TestCheckOverspend:
    def test_detects_overspend(
        self, db: Session, test_user: User, system_categories
    ):
        groceries_cat = next(c for c in system_categories if c.name == "Groceries")

        set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Groceries",
            amount=100.0,
            month="2024-06",
        )

        txn = Transaction(
            user_id=test_user.id,
            category_id=groceries_cat.id,
            type="expense",
            amount=Decimal("120.00"),
            category="Groceries",
            transaction_date=date(2024, 6, 10),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(txn)
        db.commit()

        alerts = check_overspend(db, test_user.id, "2024-06", threshold_percentage=80.0)
        assert len(alerts) == 1
        assert alerts[0]["category"] == "Groceries"
        assert alerts[0]["is_over"] is True
        assert alerts[0]["percentage"] == 120.0

    def test_detects_warning_threshold(
        self, db: Session, test_user: User, system_categories
    ):
        groceries_cat = next(c for c in system_categories if c.name == "Groceries")

        set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Groceries",
            amount=100.0,
            month="2024-06",
        )

        txn = Transaction(
            user_id=test_user.id,
            category_id=groceries_cat.id,
            type="expense",
            amount=Decimal("85.00"),
            category="Groceries",
            transaction_date=date(2024, 6, 10),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(txn)
        db.commit()

        alerts = check_overspend(db, test_user.id, "2024-06", threshold_percentage=80.0)
        assert len(alerts) == 1
        assert alerts[0]["is_over"] is False
        assert alerts[0]["percentage"] == 85.0

    def test_no_alerts_when_under_threshold(
        self, db: Session, test_user: User, system_categories
    ):
        groceries_cat = next(c for c in system_categories if c.name == "Groceries")

        set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Groceries",
            amount=100.0,
            month="2024-06",
        )

        txn = Transaction(
            user_id=test_user.id,
            category_id=groceries_cat.id,
            type="expense",
            amount=Decimal("50.00"),
            category="Groceries",
            transaction_date=date(2024, 6, 10),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(txn)
        db.commit()

        alerts = check_overspend(db, test_user.id, "2024-06", threshold_percentage=80.0)
        assert len(alerts) == 0

    def test_no_alerts_when_no_budgets(self, db: Session, test_user: User):
        alerts = check_overspend(db, test_user.id, "2024-06")
        assert alerts == []


class TestGetBudgetSummary:
    def test_summary_totals(
        self, db: Session, test_user: User, system_categories
    ):
        groceries_cat = next(c for c in system_categories if c.name == "Groceries")
        rent_cat = next(c for c in system_categories if c.name == "Rent")

        set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Groceries",
            amount=500.0,
            month="2024-06",
        )
        set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Rent",
            amount=1200.0,
            month="2024-06",
        )

        txn1 = Transaction(
            user_id=test_user.id,
            category_id=groceries_cat.id,
            type="expense",
            amount=Decimal("200.00"),
            category="Groceries",
            transaction_date=date(2024, 6, 15),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        txn2 = Transaction(
            user_id=test_user.id,
            category_id=rent_cat.id,
            type="expense",
            amount=Decimal("1200.00"),
            category="Rent",
            transaction_date=date(2024, 6, 1),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add_all([txn1, txn2])
        db.commit()

        summary = get_budget_summary(db, test_user.id, "2024-06")
        assert summary["total_budgeted"] == 1700.0
        assert summary["total_spent"] == 1400.0
        assert summary["total_remaining"] == 300.0
        assert summary["budget_count"] == 2

    def test_summary_with_no_budgets(self, db: Session, test_user: User):
        summary = get_budget_summary(db, test_user.id, "2024-01")
        assert summary["total_budgeted"] == 0
        assert summary["total_spent"] == 0
        assert summary["total_remaining"] == 0
        assert summary["budget_count"] == 0


class TestBudgetIncomeNotCounted:
    def test_income_transactions_not_counted_as_spent(
        self, db: Session, test_user: User, system_categories
    ):
        salary_cat = next(c for c in system_categories if c.name == "Salary")

        set_budget(
            db=db,
            user_id=test_user.id,
            category_name="Salary",
            amount=5000.0,
            month="2024-06",
        )

        txn = Transaction(
            user_id=test_user.id,
            category_id=salary_cat.id,
            type="income",
            amount=Decimal("3000.00"),
            category="Salary",
            transaction_date=date(2024, 6, 1),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(txn)
        db.commit()

        budgets = get_budgets_for_month(db, test_user.id, "2024-06")
        assert len(budgets) == 1
        assert budgets[0]["spent"] == 0.0
        assert budgets[0]["remaining"] == 5000.0