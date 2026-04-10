import logging
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from database import get_db
from models.category import Category
from models.transaction import Transaction

logger = logging.getLogger(__name__)


def get_categories_for_user(db: Session, user_id: str) -> list[Category]:
    """Get all categories available to a user (system + custom)."""
    stmt = select(Category).where(
        (Category.is_system == True) | (Category.user_id == user_id)
    ).order_by(Category.is_system.desc(), Category.name.asc())
    result = db.execute(stmt)
    categories = list(result.scalars().all())
    return categories


def get_system_categories(db: Session) -> list[Category]:
    """Get all system-wide categories."""
    stmt = select(Category).where(
        Category.is_system == True
    ).order_by(Category.name.asc())
    result = db.execute(stmt)
    return list(result.scalars().all())


def get_custom_categories(db: Session, user_id: str) -> list[Category]:
    """Get custom categories for a specific user."""
    stmt = select(Category).where(
        Category.user_id == user_id,
        Category.is_system == False,
    ).order_by(Category.name.asc())
    result = db.execute(stmt)
    return list(result.scalars().all())


def get_category_by_id(db: Session, category_id: str) -> Optional[Category]:
    """Get a single category by its ID."""
    stmt = select(Category).where(Category.id == category_id)
    result = db.execute(stmt)
    return result.scalars().first()


def get_category_by_name_and_user(
    db: Session, name: str, user_id: Optional[str]
) -> Optional[Category]:
    """Get a category by name for a specific user or system category."""
    if user_id is None:
        stmt = select(Category).where(
            Category.name == name,
            Category.is_system == True,
        )
    else:
        stmt = select(Category).where(
            Category.name == name,
            Category.user_id == user_id,
        )
    result = db.execute(stmt)
    return result.scalars().first()


def get_category_transaction_count(db: Session, category_id: str) -> int:
    """Count the number of transactions associated with a category."""
    stmt = select(func.count()).select_from(Transaction).where(
        Transaction.category_id == category_id
    )
    result = db.execute(stmt)
    count = result.scalar()
    return count if count is not None else 0


def create_category(
    db: Session,
    user_id: str,
    name: str,
    description: Optional[str] = None,
    color: Optional[str] = None,
    icon: Optional[str] = None,
    is_active: bool = True,
) -> Category:
    """Create a new custom category for a user."""
    existing = get_category_by_name_and_user(db, name, user_id)
    if existing is not None:
        raise ValueError(f"Category '{name}' already exists for this user.")

    category = Category(
        name=name.strip(),
        type="expense",
        color=color,
        icon=icon,
        is_system=False,
        user_id=user_id,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    logger.info("Created custom category '%s' (id=%s) for user %s", name, category.id, user_id)
    return category


def update_category(
    db: Session,
    category_id: str,
    user_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[str] = None,
    icon: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[Category]:
    """Update a custom category owned by the user."""
    category = get_category_by_id(db, category_id)
    if category is None:
        logger.warning("Category %s not found for update", category_id)
        return None

    if category.is_system:
        raise ValueError("System categories cannot be updated by users.")

    if category.user_id != user_id:
        raise PermissionError("You do not have permission to update this category.")

    if name is not None:
        stripped_name = name.strip()
        if stripped_name and stripped_name != category.name:
            existing = get_category_by_name_and_user(db, stripped_name, user_id)
            if existing is not None and existing.id != category_id:
                raise ValueError(f"Category '{stripped_name}' already exists for this user.")
            category.name = stripped_name

    if color is not None:
        category.color = color if color else None

    if icon is not None:
        category.icon = icon if icon else None

    db.commit()
    db.refresh(category)
    logger.info("Updated custom category '%s' (id=%s) for user %s", category.name, category.id, user_id)
    return category


def delete_category(
    db: Session,
    category_id: str,
    user_id: str,
) -> bool:
    """Delete a custom category and reassign its transactions to 'Other'."""
    category = get_category_by_id(db, category_id)
    if category is None:
        logger.warning("Category %s not found for deletion", category_id)
        return False

    if category.is_system:
        raise ValueError("System categories cannot be deleted by users.")

    if category.user_id != user_id:
        raise PermissionError("You do not have permission to delete this category.")

    other_category = _get_or_create_other_category(db, user_id)

    stmt = (
        update(Transaction)
        .where(Transaction.category_id == category_id)
        .values(category_id=other_category.id, category=other_category.name)
    )
    db.execute(stmt)

    category_name = category.name
    db.delete(category)
    db.commit()
    logger.info(
        "Deleted custom category '%s' (id=%s) for user %s; transactions reassigned to 'Other'",
        category_name,
        category_id,
        user_id,
    )
    return True


def create_system_category(
    db: Session,
    name: str,
    description: Optional[str] = None,
    color: Optional[str] = None,
    icon: Optional[str] = None,
    is_active: bool = True,
) -> Category:
    """Create a new system-wide category (admin only)."""
    existing = get_category_by_name_and_user(db, name, None)
    if existing is not None:
        raise ValueError(f"System category '{name}' already exists.")

    category = Category(
        name=name.strip(),
        type="expense",
        color=color,
        icon=icon,
        is_system=True,
        user_id=None,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    logger.info("Created system category '%s' (id=%s)", name, category.id)
    return category


def update_system_category(
    db: Session,
    category_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[str] = None,
    icon: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Optional[Category]:
    """Update a system-wide category (admin only)."""
    category = get_category_by_id(db, category_id)
    if category is None:
        logger.warning("System category %s not found for update", category_id)
        return None

    if not category.is_system:
        raise ValueError("This is not a system category.")

    if name is not None:
        stripped_name = name.strip()
        if stripped_name and stripped_name != category.name:
            existing = get_category_by_name_and_user(db, stripped_name, None)
            if existing is not None and existing.id != category_id:
                raise ValueError(f"System category '{stripped_name}' already exists.")
            category.name = stripped_name

    if color is not None:
        category.color = color if color else None

    if icon is not None:
        category.icon = icon if icon else None

    db.commit()
    db.refresh(category)
    logger.info("Updated system category '%s' (id=%s)", category.name, category.id)
    return category


def delete_system_category(
    db: Session,
    category_id: str,
) -> bool:
    """Delete a system-wide category (admin only). Reassign transactions to system 'Other'."""
    category = get_category_by_id(db, category_id)
    if category is None:
        logger.warning("System category %s not found for deletion", category_id)
        return False

    if not category.is_system:
        raise ValueError("This is not a system category.")

    other_category = _get_or_create_system_other_category(db)

    if category.id == other_category.id:
        raise ValueError("Cannot delete the 'Other' system category.")

    stmt = (
        update(Transaction)
        .where(Transaction.category_id == category_id)
        .values(category_id=other_category.id, category=other_category.name)
    )
    db.execute(stmt)

    category_name = category.name
    db.delete(category)
    db.commit()
    logger.info(
        "Deleted system category '%s' (id=%s); transactions reassigned to system 'Other'",
        category_name,
        category_id,
    )
    return True


def get_categories_with_transaction_counts(
    db: Session, user_id: str
) -> list[dict]:
    """Get categories with their transaction counts for a user."""
    categories = get_categories_for_user(db, user_id)
    result = []
    for cat in categories:
        count = get_category_transaction_count(db, cat.id)
        result.append({
            "id": cat.id,
            "name": cat.name,
            "type": cat.type,
            "color": cat.color,
            "icon": cat.icon,
            "is_system": cat.is_system,
            "is_active": True,
            "user_id": cat.user_id,
            "created_at": cat.created_at,
            "transaction_count": count,
            "description": None,
        })
    return result


def get_system_categories_with_transaction_counts(db: Session) -> list[dict]:
    """Get system categories with their transaction counts."""
    categories = get_system_categories(db)
    result = []
    for cat in categories:
        count = get_category_transaction_count(db, cat.id)
        result.append({
            "id": cat.id,
            "name": cat.name,
            "type": cat.type,
            "color": cat.color,
            "icon": cat.icon,
            "is_system": cat.is_system,
            "is_active": True,
            "user_id": cat.user_id,
            "created_at": cat.created_at,
            "transaction_count": count,
            "description": None,
        })
    return result


def _get_or_create_other_category(db: Session, user_id: str) -> Category:
    """Get or create an 'Other' category for a user."""
    existing = get_category_by_name_and_user(db, "Other", user_id)
    if existing is not None:
        return existing

    system_other = _get_or_create_system_other_category(db)
    return system_other


def _get_or_create_system_other_category(db: Session) -> Category:
    """Get or create a system-wide 'Other' category."""
    stmt = select(Category).where(
        Category.name == "Other",
        Category.is_system == True,
    )
    result = db.execute(stmt)
    existing = result.scalars().first()
    if existing is not None:
        return existing

    category = Category(
        name="Other",
        type="expense",
        color="#6B7280",
        icon=None,
        is_system=True,
        user_id=None,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    logger.info("Created system 'Other' category (id=%s)", category.id)
    return category


def seed_default_categories(db: Session) -> None:
    """Seed default system categories if none exist."""
    stmt = select(func.count()).select_from(Category).where(Category.is_system == True)
    result = db.execute(stmt)
    count = result.scalar()
    if count is not None and count > 0:
        logger.info("System categories already exist (%d found), skipping seed.", count)
        return

    defaults = [
        {"name": "Salary", "type": "income", "color": "#22C55E", "icon": "💰"},
        {"name": "Freelance", "type": "income", "color": "#16A34A", "icon": "💻"},
        {"name": "Investments", "type": "income", "color": "#15803D", "icon": "📈"},
        {"name": "Groceries", "type": "expense", "color": "#EF4444", "icon": "🛒"},
        {"name": "Rent", "type": "expense", "color": "#DC2626", "icon": "🏠"},
        {"name": "Utilities", "type": "expense", "color": "#F59E0B", "icon": "💡"},
        {"name": "Transportation", "type": "expense", "color": "#3B82F6", "icon": "🚗"},
        {"name": "Entertainment", "type": "expense", "color": "#8B5CF6", "icon": "🎬"},
        {"name": "Healthcare", "type": "expense", "color": "#EC4899", "icon": "🏥"},
        {"name": "Education", "type": "expense", "color": "#6366F1", "icon": "📚"},
        {"name": "Shopping", "type": "expense", "color": "#F97316", "icon": "🛍️"},
        {"name": "Dining", "type": "expense", "color": "#E11D48", "icon": "🍽️"},
        {"name": "Other", "type": "expense", "color": "#6B7280", "icon": None},
    ]

    for cat_data in defaults:
        category = Category(
            name=cat_data["name"],
            type=cat_data["type"],
            color=cat_data["color"],
            icon=cat_data["icon"],
            is_system=True,
            user_id=None,
        )
        db.add(category)

    db.commit()
    logger.info("Seeded %d default system categories.", len(defaults))