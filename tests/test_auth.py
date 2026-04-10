import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from database import Base, get_db
from main import app
from models.user import User
from utils.security import hash_password

TEST_DATABASE_URL = "sqlite:///./test_wealthwise.db"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def existing_user(db_session: Session):
    user = User(
        username="existinguser",
        email="existing@example.com",
        full_name="Existing User",
        password_hash=hash_password("ValidPass1"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session: Session):
    user = User(
        username="inactiveuser",
        email="inactive@example.com",
        full_name="Inactive User",
        password_hash=hash_password("ValidPass1"),
        role="user",
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestRegistrationPage:
    def test_get_register_page_returns_200(self, client: TestClient):
        response = client.get("/auth/register")
        assert response.status_code == 200
        assert "Create your account" in response.text

    def test_get_register_page_redirects_if_authenticated(
        self, client: TestClient, existing_user: User
    ):
        login_response = client.post(
            "/auth/login",
            data={
                "email": "existing@example.com",
                "password": "ValidPass1",
            },
        )
        cookies = login_response.cookies

        response = client.get("/auth/register", cookies=cookies)
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"


class TestRegistrationSubmit:
    def test_register_valid_user_redirects_to_login(self, client: TestClient):
        response = client.post(
            "/auth/register",
            data={
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "StrongPass1",
                "confirm_password": "StrongPass1",
                "display_name": "New User",
            },
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/auth/login"

    def test_register_creates_user_in_database(
        self, client: TestClient, db_session: Session
    ):
        client.post(
            "/auth/register",
            data={
                "email": "dbcheck@example.com",
                "username": "dbcheckuser",
                "password": "StrongPass1",
                "confirm_password": "StrongPass1",
                "display_name": "",
            },
        )
        user = db_session.query(User).filter(User.email == "dbcheck@example.com").first()
        assert user is not None
        assert user.username == "dbcheckuser"
        assert user.role == "user"
        assert user.is_active is True

    def test_register_duplicate_email_shows_error(
        self, client: TestClient, existing_user: User
    ):
        response = client.post(
            "/auth/register",
            data={
                "email": "existing@example.com",
                "username": "differentuser",
                "password": "StrongPass1",
                "confirm_password": "StrongPass1",
                "display_name": "",
            },
        )
        assert response.status_code == 200
        assert "already exists" in response.text

    def test_register_duplicate_username_shows_error(
        self, client: TestClient, existing_user: User
    ):
        response = client.post(
            "/auth/register",
            data={
                "email": "different@example.com",
                "username": "existinguser",
                "password": "StrongPass1",
                "confirm_password": "StrongPass1",
                "display_name": "",
            },
        )
        assert response.status_code == 200
        assert "already exists" in response.text

    def test_register_password_too_short_shows_error(self, client: TestClient):
        response = client.post(
            "/auth/register",
            data={
                "email": "short@example.com",
                "username": "shortpwduser",
                "password": "Ab1",
                "confirm_password": "Ab1",
                "display_name": "",
            },
        )
        assert response.status_code == 200
        assert "at least 8 characters" in response.text

    def test_register_password_no_uppercase_shows_error(self, client: TestClient):
        response = client.post(
            "/auth/register",
            data={
                "email": "noupper@example.com",
                "username": "noupperuser",
                "password": "alllowercase1",
                "confirm_password": "alllowercase1",
                "display_name": "",
            },
        )
        assert response.status_code == 200
        assert "uppercase" in response.text

    def test_register_password_no_lowercase_shows_error(self, client: TestClient):
        response = client.post(
            "/auth/register",
            data={
                "email": "nolower@example.com",
                "username": "noloweruser",
                "password": "ALLUPPERCASE1",
                "confirm_password": "ALLUPPERCASE1",
                "display_name": "",
            },
        )
        assert response.status_code == 200
        assert "lowercase" in response.text

    def test_register_password_no_digit_shows_error(self, client: TestClient):
        response = client.post(
            "/auth/register",
            data={
                "email": "nodigit@example.com",
                "username": "nodigituser",
                "password": "NoDigitHere",
                "confirm_password": "NoDigitHere",
                "display_name": "",
            },
        )
        assert response.status_code == 200
        assert "digit" in response.text

    def test_register_passwords_do_not_match_shows_error(self, client: TestClient):
        response = client.post(
            "/auth/register",
            data={
                "email": "mismatch@example.com",
                "username": "mismatchuser",
                "password": "StrongPass1",
                "confirm_password": "DifferentPass2",
                "display_name": "",
            },
        )
        assert response.status_code == 200
        assert "do not match" in response.text

    def test_register_username_too_short_shows_error(self, client: TestClient):
        response = client.post(
            "/auth/register",
            data={
                "email": "shortname@example.com",
                "username": "ab",
                "password": "StrongPass1",
                "confirm_password": "StrongPass1",
                "display_name": "",
            },
        )
        assert response.status_code == 200
        assert "at least 3 characters" in response.text

    def test_register_username_invalid_characters_shows_error(self, client: TestClient):
        response = client.post(
            "/auth/register",
            data={
                "email": "badchars@example.com",
                "username": "bad user!",
                "password": "StrongPass1",
                "confirm_password": "StrongPass1",
                "display_name": "",
            },
        )
        assert response.status_code == 200
        assert "alphanumeric" in response.text

    def test_register_preserves_form_data_on_error(self, client: TestClient):
        response = client.post(
            "/auth/register",
            data={
                "email": "preserve@example.com",
                "username": "ab",
                "password": "StrongPass1",
                "confirm_password": "StrongPass1",
                "display_name": "Preserved Name",
            },
        )
        assert response.status_code == 200
        assert "preserve@example.com" in response.text
        assert "Preserved Name" in response.text


class TestLoginPage:
    def test_get_login_page_returns_200(self, client: TestClient):
        response = client.get("/auth/login")
        assert response.status_code == 200
        assert "Sign in to WealthWise" in response.text

    def test_get_login_page_redirects_if_authenticated(
        self, client: TestClient, existing_user: User
    ):
        login_response = client.post(
            "/auth/login",
            data={
                "email": "existing@example.com",
                "password": "ValidPass1",
            },
        )
        cookies = login_response.cookies

        response = client.get("/auth/login", cookies=cookies)
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"


class TestLoginSubmit:
    def test_login_valid_credentials_redirects_to_dashboard(
        self, client: TestClient, existing_user: User
    ):
        response = client.post(
            "/auth/login",
            data={
                "email": "existing@example.com",
                "password": "ValidPass1",
            },
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"

    def test_login_sets_access_token_cookie(
        self, client: TestClient, existing_user: User
    ):
        response = client.post(
            "/auth/login",
            data={
                "email": "existing@example.com",
                "password": "ValidPass1",
            },
        )
        assert "access_token" in response.cookies

    def test_login_with_remember_me_sets_longer_cookie(
        self, client: TestClient, existing_user: User
    ):
        response = client.post(
            "/auth/login",
            data={
                "email": "existing@example.com",
                "password": "ValidPass1",
                "remember_me": "on",
            },
        )
        assert response.status_code == 303
        assert "access_token" in response.cookies

    def test_login_wrong_password_shows_error(
        self, client: TestClient, existing_user: User
    ):
        response = client.post(
            "/auth/login",
            data={
                "email": "existing@example.com",
                "password": "WrongPassword1",
            },
        )
        assert response.status_code == 200
        assert "Invalid email or password" in response.text

    def test_login_nonexistent_email_shows_error(self, client: TestClient):
        response = client.post(
            "/auth/login",
            data={
                "email": "nobody@example.com",
                "password": "SomePass1",
            },
        )
        assert response.status_code == 200
        assert "Invalid email or password" in response.text

    def test_login_inactive_user_shows_error(
        self, client: TestClient, inactive_user: User
    ):
        response = client.post(
            "/auth/login",
            data={
                "email": "inactive@example.com",
                "password": "ValidPass1",
            },
        )
        assert response.status_code == 200
        assert "Invalid email or password" in response.text

    def test_login_email_case_insensitive(
        self, client: TestClient, existing_user: User
    ):
        response = client.post(
            "/auth/login",
            data={
                "email": "EXISTING@EXAMPLE.COM",
                "password": "ValidPass1",
            },
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/dashboard"

    def test_login_sets_flash_message_cookie(
        self, client: TestClient, existing_user: User
    ):
        response = client.post(
            "/auth/login",
            data={
                "email": "existing@example.com",
                "password": "ValidPass1",
            },
        )
        assert "flash_messages" in response.cookies


class TestLogout:
    def test_logout_get_redirects_to_login(
        self, client: TestClient, existing_user: User
    ):
        login_response = client.post(
            "/auth/login",
            data={
                "email": "existing@example.com",
                "password": "ValidPass1",
            },
        )
        cookies = login_response.cookies

        response = client.get("/auth/logout", cookies=cookies)
        assert response.status_code == 303
        assert response.headers["location"] == "/auth/login"

    def test_logout_post_redirects_to_login(
        self, client: TestClient, existing_user: User
    ):
        login_response = client.post(
            "/auth/login",
            data={
                "email": "existing@example.com",
                "password": "ValidPass1",
            },
        )
        cookies = login_response.cookies

        response = client.post("/auth/logout", cookies=cookies)
        assert response.status_code == 303
        assert response.headers["location"] == "/auth/login"

    def test_logout_clears_access_token_cookie(
        self, client: TestClient, existing_user: User
    ):
        login_response = client.post(
            "/auth/login",
            data={
                "email": "existing@example.com",
                "password": "ValidPass1",
            },
        )
        cookies = login_response.cookies

        response = client.get("/auth/logout", cookies=cookies)
        set_cookie_headers = response.headers.get_list("set-cookie")
        access_token_cleared = any(
            "access_token" in header and ('=""' in header or "max-age=0" in header.lower() or 'expires=' in header.lower())
            for header in set_cookie_headers
        )
        assert access_token_cleared or "access_token" not in response.cookies

    def test_logout_sets_flash_message(
        self, client: TestClient, existing_user: User
    ):
        login_response = client.post(
            "/auth/login",
            data={
                "email": "existing@example.com",
                "password": "ValidPass1",
            },
        )
        cookies = login_response.cookies

        response = client.get("/auth/logout", cookies=cookies)
        assert "flash_messages" in response.cookies


class TestJWTCookie:
    def test_access_token_is_httponly(
        self, client: TestClient, existing_user: User
    ):
        response = client.post(
            "/auth/login",
            data={
                "email": "existing@example.com",
                "password": "ValidPass1",
            },
        )
        set_cookie_headers = response.headers.get_list("set-cookie")
        access_token_header = None
        for header in set_cookie_headers:
            if "access_token" in header and "flash" not in header:
                access_token_header = header
                break
        assert access_token_header is not None
        assert "httponly" in access_token_header.lower()

    def test_access_token_has_samesite_lax(
        self, client: TestClient, existing_user: User
    ):
        response = client.post(
            "/auth/login",
            data={
                "email": "existing@example.com",
                "password": "ValidPass1",
            },
        )
        set_cookie_headers = response.headers.get_list("set-cookie")
        access_token_header = None
        for header in set_cookie_headers:
            if "access_token" in header and "flash" not in header:
                access_token_header = header
                break
        assert access_token_header is not None
        assert "samesite=lax" in access_token_header.lower()

    def test_authenticated_user_can_access_dashboard(
        self, client: TestClient, existing_user: User
    ):
        login_response = client.post(
            "/auth/login",
            data={
                "email": "existing@example.com",
                "password": "ValidPass1",
            },
        )
        cookies = login_response.cookies

        response = client.get("/dashboard", cookies=cookies)
        assert response.status_code == 200

    def test_unauthenticated_user_cannot_access_dashboard(self, client: TestClient):
        response = client.get("/dashboard")
        assert response.status_code == 303
        assert "/auth/login" in response.headers.get("location", "")


class TestRegistrationAndLogin:
    def test_register_then_login_flow(self, client: TestClient):
        reg_response = client.post(
            "/auth/register",
            data={
                "email": "flowtest@example.com",
                "username": "flowtestuser",
                "password": "FlowTest1",
                "confirm_password": "FlowTest1",
                "display_name": "Flow Test",
            },
        )
        assert reg_response.status_code == 303

        login_response = client.post(
            "/auth/login",
            data={
                "email": "flowtest@example.com",
                "password": "FlowTest1",
            },
        )
        assert login_response.status_code == 303
        assert login_response.headers["location"] == "/dashboard"
        assert "access_token" in login_response.cookies

    def test_register_stores_email_lowercase(
        self, client: TestClient, db_session: Session
    ):
        client.post(
            "/auth/register",
            data={
                "email": "UPPERCASE@EXAMPLE.COM",
                "username": "uppercaseuser",
                "password": "StrongPass1",
                "confirm_password": "StrongPass1",
                "display_name": "",
            },
        )
        user = db_session.query(User).filter(User.username == "uppercaseuser").first()
        assert user is not None
        assert user.email == "uppercase@example.com"

    def test_register_stores_hashed_password(
        self, client: TestClient, db_session: Session
    ):
        client.post(
            "/auth/register",
            data={
                "email": "hashcheck@example.com",
                "username": "hashcheckuser",
                "password": "StrongPass1",
                "confirm_password": "StrongPass1",
                "display_name": "",
            },
        )
        user = db_session.query(User).filter(User.email == "hashcheck@example.com").first()
        assert user is not None
        assert user.password_hash != "StrongPass1"
        assert user.password_hash.startswith("$2b$") or user.password_hash.startswith("$2a$")