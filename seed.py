import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine
from models.user import User
from models.category import Category
from utils.security import hash_password

logger = logging.getLogger(__name__)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@wealthwise.com")

DEFAULT_CATEGORIES = [
    {"name": "Salary", "type": "income", "color": "#22C55E", "icon": "💰"},
    {"name": "Freelance", "type": "income", "color": "#16A34A", "icon": "💻"},
    {"name": "Investments", "type": "income", "color": "#15803D", "icon": "📈"},
    {"name": "Groceries", "type": "expense", "color": "#EF4444", "icon": "🛒"},
    {"name": "Food", "type": "expense", "color": "#DC2626", "icon": "🍔"},
    {"name": "Rent", "type": "expense", "color": "#B91C1C", "icon": "🏠"},
    {"name": "Utilities", "type": "expense", "color": "#F59E0B", "icon": "💡"},
    {"name": "Transportation", "type": "expense", "color": "#3B82F6", "icon": "🚗"},
    {"name": "Transport", "type": "expense", "color": "#2563EB", "icon": "🚌"},
    {"name": "Entertainment", "type": "expense", "color": "#8B5CF6", "icon": "🎬"},
    {"name": "Healthcare", "type": "expense", "color": "#EC4899", "icon": "🏥"},
    {"name": "Education", "type": "expense", "color": "#6366F1", "icon": "📚"},
    {"name": "Shopping", "type": "expense", "color": "#F97316", "icon": "🛍️"},
    {"name": "Dining", "type": "expense", "color": "#E11D48", "icon": "🍽️"},
    {"name": "Other", "type": "expense", "color": "#6B7280", "icon": None},
]


def seed_admin_user(db: Session) -> None:
    """Idempotently create the default admin user from environment variables."""
    existing_admin = db.execute(
        select(User).where(User.email == ADMIN_EMAIL)
    ).scalars().first()

    if existing_admin is not None:
        logger.info(
            "Admin user '%s' already exists (id=%s), skipping creation.",
            existing_admin.username,
            existing_admin.id,
        )
        return

    existing_username = db.execute(
        select(User).where(User.username == ADMIN_USERNAME)
    ).scalars().first()

    if existing_username is not None:
        logger.info(
            "User with username '%s' already exists (id=%s), skipping admin creation.",
            ADMIN_USERNAME,
            existing_username.id,
        )
        return

    now = datetime.now(timezone.utc)
    admin_user = User(
        username=ADMIN_USERNAME,
        email=ADMIN_EMAIL,
        full_name="System Administrator",
        password_hash=hash_password(ADMIN_PASSWORD),
        role="admin",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    logger.info(
        "Created default admin user '%s' (id=%s, email=%s).",
        admin_user.username,
        admin_user.id,
        admin_user.email,
    )


def seed_system_categories(db: Session) -> None:
    """Idempotently create default system categories."""
    count_result = db.execute(
        select(func.count()).select_from(Category).where(Category.is_system == True)
    ).scalar()

    if count_result is not None and count_result > 0:
        logger.info(
            "System categories already exist (%d found), checking for missing categories.",
            count_result,
        )
        existing_names_result = db.execute(
            select(Category.name).where(Category.is_system == True)
        ).scalars().all()
        existing_names = set(existing_names_result)

        added_count = 0
        for cat_data in DEFAULT_CATEGORIES:
            if cat_data["name"] not in existing_names:
                now = datetime.now(timezone.utc)
                category = Category(
                    name=cat_data["name"],
                    type=cat_data["type"],
                    color=cat_data["color"],
                    icon=cat_data["icon"],
                    is_system=True,
                    user_id=None,
                    created_at=now,
                )
                db.add(category)
                added_count += 1
                logger.info("Adding missing system category '%s'.", cat_data["name"])

        if added_count > 0:
            db.commit()
            logger.info("Added %d missing system categories.", added_count)
        else:
            logger.info("All default system categories already present.")
        return

    now = datetime.now(timezone.utc)
    for cat_data in DEFAULT_CATEGORIES:
        category = Category(
            name=cat_data["name"],
            type=cat_data["type"],
            color=cat_data["color"],
            icon=cat_data["icon"],
            is_system=True,
            user_id=None,
            created_at=now,
        )
        db.add(category)

    db.commit()
    logger.info("Seeded %d default system categories.", len(DEFAULT_CATEGORIES))


def seed_database() -> None:
    """Run all seed operations. Safe to call multiple times (idempotent)."""
    logger.info("Starting database seeding...")

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_admin_user(db)
        seed_system_categories(db)
        logger.info("Database seeding completed successfully.")
    except Exception:
        db.rollback()
        logger.exception("Error during database seeding.")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-5.5s [%(name)s] %(message)s",
    )
    seed_database()