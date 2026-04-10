import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

logger = logging.getLogger(__name__)


def register_user(
    db: Session,
    username: str,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    role: str = "user",
) -> User:
    """
    Register a new user after validating uniqueness of username and email.
    Hashes the password before storing.
    Returns the created User object.
    Raises ValueError if username or email already exists.
    """
    email = email.lower().strip()
    username = username.strip()

    existing_email = db.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalars().first()
    if existing_email is not None:
        raise ValueError("A user with this email already exists.")

    existing_username = db.execute(
        select(User).where(func.lower(User.username) == func.lower(username))
    ).scalars().first()
    if existing_username is not None:
        raise ValueError("A user with this username already exists.")

    password_hash = hash_password(password)

    user = User(
        username=username,
        email=email,
        full_name=full_name if full_name and full_name.strip() else None,
        password_hash=password_hash,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(
        "Registered new user '%s' (id=%s, email=%s, role=%s)",
        user.username,
        user.id,
        user.email,
        user.role,
    )
    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> Optional[User]:
    """
    Authenticate a user by email and password.
    Returns the User object if credentials are valid, None otherwise.
    """
    email = email.lower().strip()

    user = db.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalars().first()

    if user is None:
        logger.warning("Authentication failed: no user found with email '%s'", email)
        return None

    if not user.is_active:
        logger.warning(
            "Authentication failed: user '%s' (id=%s) is deactivated",
            user.username,
            user.id,
        )
        return None

    if not verify_password(password, user.password_hash):
        logger.warning(
            "Authentication failed: invalid password for user '%s' (id=%s)",
            user.username,
            user.id,
        )
        return None

    logger.info("User '%s' (id=%s) authenticated successfully", user.username, user.id)
    return user


def create_user_access_token(user: User) -> str:
    """
    Create a JWT access token for the given user.
    Returns the encoded JWT string.
    """
    token_data = {
        "sub": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(data=token_data, expires_delta=expires_delta)
    return token


def get_user_by_id(
    db: Session,
    user_id: str,
) -> Optional[User]:
    """
    Retrieve a user by their ID.
    Returns the User object or None if not found.
    """
    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalars().first()
    return user


def get_user_by_email(
    db: Session,
    email: str,
) -> Optional[User]:
    """
    Retrieve a user by their email address.
    Returns the User object or None if not found.
    """
    email = email.lower().strip()
    user = db.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalars().first()
    return user


def get_user_by_username(
    db: Session,
    username: str,
) -> Optional[User]:
    """
    Retrieve a user by their username.
    Returns the User object or None if not found.
    """
    username = username.strip()
    user = db.execute(
        select(User).where(func.lower(User.username) == func.lower(username))
    ).scalars().first()
    return user


def update_user_profile(
    db: Session,
    user_id: str,
    username: Optional[str] = None,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
) -> Optional[User]:
    """
    Update a user's profile information.
    Validates uniqueness of username and email if changed.
    Returns the updated User object or None if user not found.
    Raises ValueError if new username or email conflicts with another user.
    """
    user = get_user_by_id(db, user_id)
    if user is None:
        logger.warning("User %s not found for profile update", user_id)
        return None

    if username is not None:
        username = username.strip()
        if username and username.lower() != user.username.lower():
            existing = db.execute(
                select(User).where(
                    func.lower(User.username) == func.lower(username),
                    User.id != user_id,
                )
            ).scalars().first()
            if existing is not None:
                raise ValueError("A user with this username already exists.")
            user.username = username

    if email is not None:
        email = email.lower().strip()
        if email and email != user.email.lower():
            existing = db.execute(
                select(User).where(
                    func.lower(User.email) == email,
                    User.id != user_id,
                )
            ).scalars().first()
            if existing is not None:
                raise ValueError("A user with this email already exists.")
            user.email = email

    if full_name is not None:
        stripped = full_name.strip()
        user.full_name = stripped if stripped else None

    db.commit()
    db.refresh(user)

    logger.info(
        "Updated profile for user '%s' (id=%s)",
        user.username,
        user.id,
    )
    return user


def change_password(
    db: Session,
    user_id: str,
    current_password: str,
    new_password: str,
) -> bool:
    """
    Change a user's password after verifying the current password.
    Returns True if the password was changed successfully, False otherwise.
    Raises ValueError if the current password is incorrect.
    """
    user = get_user_by_id(db, user_id)
    if user is None:
        logger.warning("User %s not found for password change", user_id)
        return False

    if not verify_password(current_password, user.password_hash):
        raise ValueError("Current password is incorrect.")

    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)

    logger.info("Password changed for user '%s' (id=%s)", user.username, user.id)
    return True


def get_all_users(db: Session) -> list[User]:
    """
    Retrieve all users in the system.
    Returns a list of User objects ordered by creation date descending.
    """
    result = db.execute(
        select(User).order_by(User.created_at.desc())
    )
    return list(result.scalars().all())


def activate_user(db: Session, user_id: str) -> Optional[User]:
    """
    Activate a user account.
    Returns the updated User object or None if not found.
    """
    user = get_user_by_id(db, user_id)
    if user is None:
        logger.warning("User %s not found for activation", user_id)
        return None

    user.is_active = True
    db.commit()
    db.refresh(user)

    logger.info("Activated user '%s' (id=%s)", user.username, user.id)
    return user


def deactivate_user(db: Session, user_id: str) -> Optional[User]:
    """
    Deactivate a user account.
    Returns the updated User object or None if not found.
    """
    user = get_user_by_id(db, user_id)
    if user is None:
        logger.warning("User %s not found for deactivation", user_id)
        return None

    user.is_active = False
    db.commit()
    db.refresh(user)

    logger.info("Deactivated user '%s' (id=%s)", user.username, user.id)
    return user


def delete_user(db: Session, user_id: str) -> bool:
    """
    Permanently delete a user account.
    Returns True if deleted, False if user not found.
    """
    user = get_user_by_id(db, user_id)
    if user is None:
        logger.warning("User %s not found for deletion", user_id)
        return False

    username = user.username
    db.delete(user)
    db.commit()

    logger.info("Deleted user '%s' (id=%s)", username, user_id)
    return True


def get_user_count(db: Session) -> int:
    """
    Get the total number of users in the system.
    """
    result = db.execute(select(func.count(User.id)))
    count = result.scalar()
    return count if count is not None else 0


def get_active_user_count(db: Session) -> int:
    """
    Get the number of active users in the system.
    """
    result = db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    count = result.scalar()
    return count if count is not None else 0