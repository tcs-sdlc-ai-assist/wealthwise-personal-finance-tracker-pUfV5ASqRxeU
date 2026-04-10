import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from datetime import date, datetime, timedelta, timezone
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
from utils.security import hash_password, create_access_token


TEST_DATABASE_URL = "sqlite:///./test_transactions.db"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def override_get_db(db_session):
    def _override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_get_db):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def test_user(db_session: Session) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        username="testuser",
        email="testuser@example.com",
        full_name="Test User",
        password_hash=hash_password("TestPass1"),
        role="user",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def second_user(db_session: Session) -> User:
    now = datetime.now(timezone.utc)
    user = User(
        username="seconduser",
        email="seconduser@example.com",
        full_name="Second User",
        password_hash=hash_password("TestPass2"),
        role="user",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_category(db_session: Session) -> Category:
    now = datetime.now(timezone.utc)
    category = Category(
        name="Groceries",
        type="expense",
        color="#EF4444",
        icon="🛒",
        is_system=True,
        user_id=None,
        created_at=now,
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture
def income_category(db_session: Session) -> Category:
    now = datetime.now(timezone.utc)
    category = Category(
        name="Salary",
        type="income",
        color="#22C55E",
        icon="💰",
        is_system=True,
        user_id=None,
        created_at=now,
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture
def auth_cookies(test_user: User) -> dict:
    token_data = {
        "sub": test_user.id,
        "username": test_user.username,
        "email": test_user.email,
        "role": test_user.role,
    }
    token = create_access_token(data=token_data, expires_delta=timedelta(minutes=30))
    return {"access_token": token}


@pytest.fixture
def second_user_cookies(second_user: User) -> dict:
    token_data = {
        "sub": second_user.id,
        "username": second_user.username,
        "email": second_user.email,
        "role": second_user.role,
    }
    token = create_access_token(data=token_data, expires_delta=timedelta(minutes=30))
    return {"access_token": token}


@pytest.fixture
def sample_transaction(db_session: Session, test_user: User, test_category: Category) -> Transaction:
    import uuid

    now = datetime.utcnow()
    txn = Transaction(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        category_id=test_category.id,
        type="expense",
        amount=Decimal("50.00"),
        category="Groceries",
        description="Weekly groceries",
        transaction_date=date.today(),
        created_at=now,
        updated_at=now,
    )
    db_session.add(txn)
    db_session.commit()
    db_session.refresh(txn)
    return txn


@pytest.fixture
def multiple_transactions(db_session: Session, test_user: User, test_category: Category, income_category: Category) -> list[Transaction]:
    import uuid

    now = datetime.utcnow()
    transactions = []

    for i in range(5):
        txn = Transaction(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            category_id=test_category.id,
            type="expense",
            amount=Decimal(str(10.00 * (i + 1))),
            category="Groceries",
            description=f"Expense transaction {i + 1}",
            transaction_date=date.today() - timedelta(days=i),
            created_at=now,
            updated_at=now,
        )
        transactions.append(txn)
        db_session.add(txn)

    for i in range(3):
        txn = Transaction(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            category_id=income_category.id,
            type="income",
            amount=Decimal(str(100.00 * (i + 1))),
            category="Salary",
            description=f"Income transaction {i + 1}",
            transaction_date=date.today() - timedelta(days=i),
            created_at=now,
            updated_at=now,
        )
        transactions.append(txn)
        db_session.add(txn)

    db_session.commit()
    for txn in transactions:
        db_session.refresh(txn)
    return transactions


class TestTransactionsList:
    """Tests for GET /transactions endpoint."""

    def test_list_transactions_requires_auth(self, client: TestClient):
        response = client.get("/transactions", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    def test_list_transactions_empty(self, client: TestClient, auth_cookies: dict, test_user: User):
        response = client.get("/transactions", cookies=auth_cookies)
        assert response.status_code == 200
        assert b"No transactions found" in response.content

    def test_list_transactions_with_data(
        self, client: TestClient, auth_cookies: dict, multiple_transactions: list[Transaction]
    ):
        response = client.get("/transactions", cookies=auth_cookies)
        assert response.status_code == 200
        assert b"Groceries" in response.content
        assert b"Salary" in response.content

    def test_list_transactions_filter_by_type_income(
        self, client: TestClient, auth_cookies: dict, multiple_transactions: list[Transaction]
    ):
        response = client.get("/transactions?type=income", cookies=auth_cookies)
        assert response.status_code == 200
        assert b"Salary" in response.content

    def test_list_transactions_filter_by_type_expense(
        self, client: TestClient, auth_cookies: dict, multiple_transactions: list[Transaction]
    ):
        response = client.get("/transactions?type=expense", cookies=auth_cookies)
        assert response.status_code == 200
        assert b"Groceries" in response.content

    def test_list_transactions_filter_by_category(
        self, client: TestClient, auth_cookies: dict, multiple_transactions: list[Transaction]
    ):
        response = client.get("/transactions?category=Groceries", cookies=auth_cookies)
        assert response.status_code == 200
        assert b"Groceries" in response.content

    def test_list_transactions_filter_by_date_range(
        self, client: TestClient, auth_cookies: dict, multiple_transactions: list[Transaction]
    ):
        today = date.today().isoformat()
        response = client.get(
            f"/transactions?date_from={today}&date_to={today}",
            cookies=auth_cookies,
        )
        assert response.status_code == 200

    def test_list_transactions_invalid_date_filter_ignored(
        self, client: TestClient, auth_cookies: dict, multiple_transactions: list[Transaction]
    ):
        response = client.get(
            "/transactions?date_from=invalid-date&date_to=also-invalid",
            cookies=auth_cookies,
        )
        assert response.status_code == 200

    def test_list_transactions_pagination_page_1(
        self, client: TestClient, auth_cookies: dict, multiple_transactions: list[Transaction]
    ):
        response = client.get("/transactions?page=1", cookies=auth_cookies)
        assert response.status_code == 200

    def test_list_transactions_shows_summary(
        self, client: TestClient, auth_cookies: dict, multiple_transactions: list[Transaction]
    ):
        response = client.get("/transactions", cookies=auth_cookies)
        assert response.status_code == 200
        assert b"Total Income" in response.content
        assert b"Total Expenses" in response.content
        assert b"Net Balance" in response.content


class TestTransactionCreate:
    """Tests for POST /transactions/create endpoint."""

    def test_create_transaction_requires_auth(self, client: TestClient):
        response = client.post(
            "/transactions/create",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "25.00",
                "transaction_date": date.today().isoformat(),
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    def test_create_expense_transaction_success(
        self, client: TestClient, auth_cookies: dict, test_user: User, test_category: Category
    ):
        response = client.post(
            "/transactions/create",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "25.50",
                "transaction_date": date.today().isoformat(),
                "description": "Lunch groceries",
            },
            cookies=auth_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/transactions" in response.headers.get("location", "")

    def test_create_income_transaction_success(
        self, client: TestClient, auth_cookies: dict, test_user: User, income_category: Category
    ):
        response = client.post(
            "/transactions/create",
            data={
                "type": "income",
                "category": "Salary",
                "amount": "5000.00",
                "transaction_date": date.today().isoformat(),
                "description": "Monthly salary",
            },
            cookies=auth_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/transactions" in response.headers.get("location", "")

    def test_create_transaction_invalid_type(
        self, client: TestClient, auth_cookies: dict, test_user: User, test_category: Category
    ):
        response = client.post(
            "/transactions/create",
            data={
                "type": "invalid_type",
                "category": "Groceries",
                "amount": "25.00",
                "transaction_date": date.today().isoformat(),
            },
            cookies=auth_cookies,
        )
        assert response.status_code == 422

    def test_create_transaction_empty_category(
        self, client: TestClient, auth_cookies: dict, test_user: User
    ):
        response = client.post(
            "/transactions/create",
            data={
                "type": "expense",
                "category": "   ",
                "amount": "25.00",
                "transaction_date": date.today().isoformat(),
            },
            cookies=auth_cookies,
        )
        assert response.status_code == 422

    def test_create_transaction_zero_amount(
        self, client: TestClient, auth_cookies: dict, test_user: User, test_category: Category
    ):
        response = client.post(
            "/transactions/create",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "0",
                "transaction_date": date.today().isoformat(),
            },
            cookies=auth_cookies,
        )
        assert response.status_code == 422

    def test_create_transaction_negative_amount(
        self, client: TestClient, auth_cookies: dict, test_user: User, test_category: Category
    ):
        response = client.post(
            "/transactions/create",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "-10.00",
                "transaction_date": date.today().isoformat(),
            },
            cookies=auth_cookies,
        )
        assert response.status_code == 422

    def test_create_transaction_invalid_amount(
        self, client: TestClient, auth_cookies: dict, test_user: User, test_category: Category
    ):
        response = client.post(
            "/transactions/create",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "not_a_number",
                "transaction_date": date.today().isoformat(),
            },
            cookies=auth_cookies,
        )
        assert response.status_code == 422

    def test_create_transaction_invalid_date(
        self, client: TestClient, auth_cookies: dict, test_user: User, test_category: Category
    ):
        response = client.post(
            "/transactions/create",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "25.00",
                "transaction_date": "not-a-date",
            },
            cookies=auth_cookies,
        )
        assert response.status_code == 422

    def test_create_transaction_without_description(
        self, client: TestClient, auth_cookies: dict, test_user: User, test_category: Category
    ):
        response = client.post(
            "/transactions/create",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "15.00",
                "transaction_date": date.today().isoformat(),
                "description": "",
            },
            cookies=auth_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/transactions" in response.headers.get("location", "")

    def test_create_transfer_transaction(
        self, client: TestClient, auth_cookies: dict, test_user: User, test_category: Category
    ):
        response = client.post(
            "/transactions/create",
            data={
                "type": "transfer",
                "category": "Groceries",
                "amount": "100.00",
                "transaction_date": date.today().isoformat(),
                "description": "Transfer between accounts",
            },
            cookies=auth_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303


class TestTransactionNewForm:
    """Tests for GET /transactions/new endpoint."""

    def test_new_transaction_form_requires_auth(self, client: TestClient):
        response = client.get("/transactions/new", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    def test_new_transaction_form_renders(
        self, client: TestClient, auth_cookies: dict, test_user: User, test_category: Category
    ):
        response = client.get("/transactions/new", cookies=auth_cookies)
        assert response.status_code == 200
        assert b"New Transaction" in response.content or b"Create New Transaction" in response.content


class TestTransactionEdit:
    """Tests for GET/POST /transactions/{id}/edit endpoint."""

    def test_edit_form_requires_auth(self, client: TestClient, sample_transaction: Transaction):
        response = client.get(
            f"/transactions/{sample_transaction.id}/edit",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    def test_edit_form_renders(
        self, client: TestClient, auth_cookies: dict, sample_transaction: Transaction
    ):
        response = client.get(
            f"/transactions/{sample_transaction.id}/edit",
            cookies=auth_cookies,
        )
        assert response.status_code == 200
        assert b"Edit Transaction" in response.content

    def test_edit_form_nonexistent_transaction(
        self, client: TestClient, auth_cookies: dict, test_user: User
    ):
        response = client.get(
            "/transactions/nonexistent-id/edit",
            cookies=auth_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/transactions" in response.headers.get("location", "")

    def test_update_transaction_success(
        self, client: TestClient, auth_cookies: dict, sample_transaction: Transaction
    ):
        response = client.post(
            f"/transactions/{sample_transaction.id}/edit",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "75.00",
                "transaction_date": date.today().isoformat(),
                "description": "Updated groceries",
            },
            cookies=auth_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/transactions" in response.headers.get("location", "")

    def test_update_transaction_change_type(
        self, client: TestClient, auth_cookies: dict, sample_transaction: Transaction, income_category: Category
    ):
        response = client.post(
            f"/transactions/{sample_transaction.id}/edit",
            data={
                "type": "income",
                "category": "Salary",
                "amount": "200.00",
                "transaction_date": date.today().isoformat(),
                "description": "Changed to income",
            },
            cookies=auth_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_update_transaction_invalid_amount(
        self, client: TestClient, auth_cookies: dict, sample_transaction: Transaction
    ):
        response = client.post(
            f"/transactions/{sample_transaction.id}/edit",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "0",
                "transaction_date": date.today().isoformat(),
            },
            cookies=auth_cookies,
        )
        assert response.status_code == 422

    def test_update_transaction_nonexistent(
        self, client: TestClient, auth_cookies: dict, test_user: User
    ):
        response = client.post(
            "/transactions/nonexistent-id/edit",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "25.00",
                "transaction_date": date.today().isoformat(),
            },
            cookies=auth_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/transactions" in response.headers.get("location", "")


class TestTransactionOwnership:
    """Tests for transaction ownership checks."""

    def test_cannot_view_other_users_transaction(
        self,
        client: TestClient,
        second_user_cookies: dict,
        sample_transaction: Transaction,
        second_user: User,
    ):
        response = client.get(
            f"/transactions/{sample_transaction.id}/edit",
            cookies=second_user_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/transactions" in response.headers.get("location", "")

    def test_cannot_update_other_users_transaction(
        self,
        client: TestClient,
        second_user_cookies: dict,
        sample_transaction: Transaction,
        second_user: User,
    ):
        response = client.post(
            f"/transactions/{sample_transaction.id}/edit",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "999.00",
                "transaction_date": date.today().isoformat(),
            },
            cookies=second_user_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/transactions" in response.headers.get("location", "")

    def test_cannot_delete_other_users_transaction(
        self,
        client: TestClient,
        second_user_cookies: dict,
        sample_transaction: Transaction,
        second_user: User,
    ):
        response = client.post(
            f"/transactions/{sample_transaction.id}/delete",
            cookies=second_user_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_user_only_sees_own_transactions(
        self,
        client: TestClient,
        db_session: Session,
        auth_cookies: dict,
        second_user_cookies: dict,
        test_user: User,
        second_user: User,
        test_category: Category,
    ):
        import uuid

        now = datetime.utcnow()
        txn_user1 = Transaction(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            category_id=test_category.id,
            type="expense",
            amount=Decimal("10.00"),
            category="Groceries",
            description="User 1 transaction",
            transaction_date=date.today(),
            created_at=now,
            updated_at=now,
        )
        txn_user2 = Transaction(
            id=str(uuid.uuid4()),
            user_id=second_user.id,
            category_id=test_category.id,
            type="expense",
            amount=Decimal("20.00"),
            category="Groceries",
            description="User 2 transaction",
            transaction_date=date.today(),
            created_at=now,
            updated_at=now,
        )
        db_session.add(txn_user1)
        db_session.add(txn_user2)
        db_session.commit()

        response1 = client.get("/transactions", cookies=auth_cookies)
        assert response1.status_code == 200
        assert b"User 1 transaction" in response1.content
        assert b"User 2 transaction" not in response1.content

        response2 = client.get("/transactions", cookies=second_user_cookies)
        assert response2.status_code == 200
        assert b"User 2 transaction" in response2.content
        assert b"User 1 transaction" not in response2.content


class TestTransactionDelete:
    """Tests for POST /transactions/{id}/delete endpoint."""

    def test_delete_transaction_requires_auth(self, client: TestClient, sample_transaction: Transaction):
        response = client.post(
            f"/transactions/{sample_transaction.id}/delete",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    def test_delete_transaction_success(
        self, client: TestClient, auth_cookies: dict, sample_transaction: Transaction
    ):
        response = client.post(
            f"/transactions/{sample_transaction.id}/delete",
            cookies=auth_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/transactions" in response.headers.get("location", "")

    def test_delete_nonexistent_transaction(
        self, client: TestClient, auth_cookies: dict, test_user: User
    ):
        response = client.post(
            "/transactions/nonexistent-id/delete",
            cookies=auth_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/transactions" in response.headers.get("location", "")

    def test_delete_transaction_removes_from_list(
        self,
        client: TestClient,
        auth_cookies: dict,
        sample_transaction: Transaction,
    ):
        client.post(
            f"/transactions/{sample_transaction.id}/delete",
            cookies=auth_cookies,
            follow_redirects=False,
        )

        response = client.get("/transactions", cookies=auth_cookies)
        assert response.status_code == 200
        assert b"Weekly groceries" not in response.content


class TestTransactionCSVExport:
    """Tests for GET /transactions/export/csv endpoint."""

    def test_csv_export_requires_auth(self, client: TestClient):
        response = client.get("/transactions/export/csv", follow_redirects=False)
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")

    def test_csv_export_empty(self, client: TestClient, auth_cookies: dict, test_user: User):
        response = client.get("/transactions/export/csv", cookies=auth_cookies)
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/csv")
        content = response.text
        assert "Date" in content
        assert "Type" in content
        assert "Category" in content
        assert "Amount" in content

    def test_csv_export_with_data(
        self, client: TestClient, auth_cookies: dict, multiple_transactions: list[Transaction]
    ):
        response = client.get("/transactions/export/csv", cookies=auth_cookies)
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/csv")
        content = response.text
        assert "Groceries" in content
        assert "Salary" in content
        lines = content.strip().split("\n")
        assert len(lines) > 1

    def test_csv_export_has_content_disposition(
        self, client: TestClient, auth_cookies: dict, test_user: User
    ):
        response = client.get("/transactions/export/csv", cookies=auth_cookies)
        assert response.status_code == 200
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition
        assert "wealthwise_transactions_" in content_disposition
        assert ".csv" in content_disposition

    def test_csv_export_with_type_filter(
        self, client: TestClient, auth_cookies: dict, multiple_transactions: list[Transaction]
    ):
        response = client.get(
            "/transactions/export/csv?type=income",
            cookies=auth_cookies,
        )
        assert response.status_code == 200
        content = response.text
        lines = content.strip().split("\n")
        header = lines[0]
        assert "Date" in header
        for line in lines[1:]:
            if line.strip():
                assert "income" in line.lower()

    def test_csv_export_with_category_filter(
        self, client: TestClient, auth_cookies: dict, multiple_transactions: list[Transaction]
    ):
        response = client.get(
            "/transactions/export/csv?category=Groceries",
            cookies=auth_cookies,
        )
        assert response.status_code == 200
        content = response.text
        lines = content.strip().split("\n")
        for line in lines[1:]:
            if line.strip():
                assert "Groceries" in line

    def test_csv_export_with_date_filter(
        self, client: TestClient, auth_cookies: dict, multiple_transactions: list[Transaction]
    ):
        today = date.today().isoformat()
        response = client.get(
            f"/transactions/export/csv?date_from={today}&date_to={today}",
            cookies=auth_cookies,
        )
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("text/csv")

    def test_csv_export_only_own_transactions(
        self,
        client: TestClient,
        db_session: Session,
        auth_cookies: dict,
        second_user_cookies: dict,
        test_user: User,
        second_user: User,
        test_category: Category,
    ):
        import uuid

        now = datetime.utcnow()
        txn_user1 = Transaction(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            category_id=test_category.id,
            type="expense",
            amount=Decimal("10.00"),
            category="Groceries",
            description="User1 CSV test",
            transaction_date=date.today(),
            created_at=now,
            updated_at=now,
        )
        txn_user2 = Transaction(
            id=str(uuid.uuid4()),
            user_id=second_user.id,
            category_id=test_category.id,
            type="expense",
            amount=Decimal("20.00"),
            category="Groceries",
            description="User2 CSV test",
            transaction_date=date.today(),
            created_at=now,
            updated_at=now,
        )
        db_session.add(txn_user1)
        db_session.add(txn_user2)
        db_session.commit()

        response = client.get("/transactions/export/csv", cookies=auth_cookies)
        content = response.text
        assert "User1 CSV test" in content
        assert "User2 CSV test" not in content


class TestTransactionServiceLayer:
    """Tests for transaction service functions directly."""

    def test_create_transaction_service(
        self, db_session: Session, test_user: User, test_category: Category
    ):
        from services.transaction_service import create_transaction

        txn = create_transaction(
            db=db_session,
            user_id=test_user.id,
            amount=Decimal("99.99"),
            type="expense",
            category="Groceries",
            description="Service test",
            transaction_date=date.today(),
        )
        assert txn is not None
        assert txn.id is not None
        assert txn.amount == Decimal("99.99")
        assert txn.type == "expense"
        assert txn.category == "Groceries"
        assert txn.user_id == test_user.id

    def test_get_transaction_by_id_service(
        self, db_session: Session, sample_transaction: Transaction, test_user: User
    ):
        from services.transaction_service import get_transaction_by_id

        txn = get_transaction_by_id(
            db=db_session,
            transaction_id=sample_transaction.id,
            user_id=test_user.id,
        )
        assert txn is not None
        assert txn.id == sample_transaction.id

    def test_get_transaction_by_id_wrong_user(
        self, db_session: Session, sample_transaction: Transaction, second_user: User
    ):
        from services.transaction_service import get_transaction_by_id

        txn = get_transaction_by_id(
            db=db_session,
            transaction_id=sample_transaction.id,
            user_id=second_user.id,
        )
        assert txn is None

    def test_get_transaction_by_id_nonexistent(
        self, db_session: Session, test_user: User
    ):
        from services.transaction_service import get_transaction_by_id

        txn = get_transaction_by_id(
            db=db_session,
            transaction_id="nonexistent-id",
            user_id=test_user.id,
        )
        assert txn is None

    def test_update_transaction_service(
        self, db_session: Session, sample_transaction: Transaction, test_user: User
    ):
        from services.transaction_service import update_transaction

        updated = update_transaction(
            db=db_session,
            transaction_id=sample_transaction.id,
            user_id=test_user.id,
            amount=Decimal("200.00"),
            description="Updated description",
        )
        assert updated is not None
        assert updated.amount == Decimal("200.00")
        assert updated.description == "Updated description"

    def test_update_transaction_wrong_user(
        self, db_session: Session, sample_transaction: Transaction, second_user: User
    ):
        from services.transaction_service import update_transaction

        updated = update_transaction(
            db=db_session,
            transaction_id=sample_transaction.id,
            user_id=second_user.id,
            amount=Decimal("999.00"),
        )
        assert updated is None

    def test_delete_transaction_service(
        self, db_session: Session, sample_transaction: Transaction, test_user: User
    ):
        from services.transaction_service import delete_transaction

        result = delete_transaction(
            db=db_session,
            transaction_id=sample_transaction.id,
            user_id=test_user.id,
        )
        assert result is True

    def test_delete_transaction_wrong_user(
        self, db_session: Session, sample_transaction: Transaction, second_user: User
    ):
        from services.transaction_service import delete_transaction

        result = delete_transaction(
            db=db_session,
            transaction_id=sample_transaction.id,
            user_id=second_user.id,
        )
        assert result is False

    def test_delete_transaction_nonexistent(
        self, db_session: Session, test_user: User
    ):
        from services.transaction_service import delete_transaction

        result = delete_transaction(
            db=db_session,
            transaction_id="nonexistent-id",
            user_id=test_user.id,
        )
        assert result is False

    def test_get_transactions_pagination(
        self, db_session: Session, test_user: User, multiple_transactions: list[Transaction]
    ):
        from services.transaction_service import get_transactions

        result = get_transactions(
            db=db_session,
            user_id=test_user.id,
            page=1,
            per_page=3,
        )
        assert result["total_count"] == 8
        assert len(result["transactions"]) == 3
        assert result["page"] == 1
        assert result["per_page"] == 3
        assert result["total_pages"] == 3

    def test_get_transactions_filter_by_type(
        self, db_session: Session, test_user: User, multiple_transactions: list[Transaction]
    ):
        from services.transaction_service import get_transactions

        result = get_transactions(
            db=db_session,
            user_id=test_user.id,
            type="income",
        )
        assert result["total_count"] == 3
        for txn in result["transactions"]:
            assert txn.type == "income"

    def test_get_transactions_filter_by_category(
        self, db_session: Session, test_user: User, multiple_transactions: list[Transaction]
    ):
        from services.transaction_service import get_transactions

        result = get_transactions(
            db=db_session,
            user_id=test_user.id,
            category="Groceries",
        )
        assert result["total_count"] == 5
        for txn in result["transactions"]:
            assert txn.category == "Groceries"

    def test_get_transactions_filter_by_date_range(
        self, db_session: Session, test_user: User, multiple_transactions: list[Transaction]
    ):
        from services.transaction_service import get_transactions

        today = date.today()
        result = get_transactions(
            db=db_session,
            user_id=test_user.id,
            date_from=today,
            date_to=today,
        )
        assert result["total_count"] > 0
        for txn in result["transactions"]:
            assert txn.transaction_date == today

    def test_get_transaction_summary(
        self, db_session: Session, test_user: User, multiple_transactions: list[Transaction]
    ):
        from services.transaction_service import get_transaction_summary

        summary = get_transaction_summary(
            db=db_session,
            user_id=test_user.id,
        )
        assert "total_income" in summary
        assert "total_expenses" in summary
        assert "net_balance" in summary
        assert "total_count" in summary
        assert summary["total_income"] > 0
        assert summary["total_expenses"] > 0
        assert summary["total_count"] == 8

    def test_get_distinct_categories(
        self, db_session: Session, test_user: User, multiple_transactions: list[Transaction]
    ):
        from services.transaction_service import get_distinct_categories

        categories = get_distinct_categories(db=db_session, user_id=test_user.id)
        assert "Groceries" in categories
        assert "Salary" in categories

    def test_export_transactions_csv_service(
        self, db_session: Session, test_user: User, multiple_transactions: list[Transaction]
    ):
        from services.transaction_service import export_transactions_csv

        csv_content = export_transactions_csv(
            db=db_session,
            user_id=test_user.id,
        )
        assert isinstance(csv_content, str)
        assert "Date" in csv_content
        assert "Type" in csv_content
        assert "Category" in csv_content
        assert "Amount" in csv_content
        lines = csv_content.strip().split("\n")
        assert len(lines) == 9  # 1 header + 8 data rows

    def test_export_transactions_csv_with_filter(
        self, db_session: Session, test_user: User, multiple_transactions: list[Transaction]
    ):
        from services.transaction_service import export_transactions_csv

        csv_content = export_transactions_csv(
            db=db_session,
            user_id=test_user.id,
            type="income",
        )
        lines = csv_content.strip().split("\n")
        assert len(lines) == 4  # 1 header + 3 income rows


class TestTransactionValidation:
    """Tests for transaction input validation edge cases."""

    def test_create_transaction_large_amount(
        self, client: TestClient, auth_cookies: dict, test_user: User, test_category: Category
    ):
        response = client.post(
            "/transactions/create",
            data={
                "type": "income",
                "category": "Groceries",
                "amount": "9999999999.99",
                "transaction_date": date.today().isoformat(),
                "description": "Large amount",
            },
            cookies=auth_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_create_transaction_small_amount(
        self, client: TestClient, auth_cookies: dict, test_user: User, test_category: Category
    ):
        response = client.post(
            "/transactions/create",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "0.01",
                "transaction_date": date.today().isoformat(),
                "description": "Tiny amount",
            },
            cookies=auth_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_create_transaction_past_date(
        self, client: TestClient, auth_cookies: dict, test_user: User, test_category: Category
    ):
        past_date = (date.today() - timedelta(days=365)).isoformat()
        response = client.post(
            "/transactions/create",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "25.00",
                "transaction_date": past_date,
                "description": "Past transaction",
            },
            cookies=auth_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_create_transaction_with_account_id(
        self, client: TestClient, auth_cookies: dict, test_user: User, test_category: Category
    ):
        response = client.post(
            "/transactions/create",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "25.00",
                "transaction_date": date.today().isoformat(),
                "description": "With account",
                "account_id": "some-account-id",
            },
            cookies=auth_cookies,
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_create_transaction_missing_required_fields(
        self, client: TestClient, auth_cookies: dict, test_user: User
    ):
        response = client.post(
            "/transactions/create",
            data={},
            cookies=auth_cookies,
        )
        assert response.status_code == 422

    def test_update_transaction_empty_category(
        self, client: TestClient, auth_cookies: dict, sample_transaction: Transaction
    ):
        response = client.post(
            f"/transactions/{sample_transaction.id}/edit",
            data={
                "type": "expense",
                "category": "   ",
                "amount": "50.00",
                "transaction_date": date.today().isoformat(),
            },
            cookies=auth_cookies,
        )
        assert response.status_code == 422

    def test_update_transaction_negative_amount(
        self, client: TestClient, auth_cookies: dict, sample_transaction: Transaction
    ):
        response = client.post(
            f"/transactions/{sample_transaction.id}/edit",
            data={
                "type": "expense",
                "category": "Groceries",
                "amount": "-50.00",
                "transaction_date": date.today().isoformat(),
            },
            cookies=auth_cookies,
        )
        assert response.status_code == 422