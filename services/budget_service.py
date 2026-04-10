import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, and_, case
from sqlalchemy.orm import Session

from database import get_db
from models.budget import Budget
from models.category import Category
from models.transaction import Transaction


def generate_uuid() -> str:
    return str(uuid.uuid4())


def get_budgets_for_month(
    db: Session,
    user_id: str,
    month: str,
    period: str = "monthly",
) -> list[dict]:
    """
    Retrieve all budgets for a user for a given month (YYYY-MM format),
    with spending totals computed via SQL aggregation.
    Returns a list of dicts with budget info + spent/remaining.
    """
    budgets = (
        db.query(Budget)
        .filter(
            Budget.user_id == user_id,
            Budget.month == month,
        )
        .all()
    )

    if not month or len(month) < 7:
        return []

    try:
        year_str, month_str = month.split("-")
        year_int = int(year_str)
        month_int = int(month_str)
    except (ValueError, IndexError):
        return []

    month_start = date(year_int, month_int, 1)
    if month_int == 12:
        month_end = date(year_int + 1, 1, 1)
    else:
        month_end = date(year_int, month_int + 1, 1)

    spending_query = (
        db.query(
            Transaction.category,
            func.coalesce(func.sum(Transaction.amount), 0).label("total_spent"),
        )
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.transaction_date >= month_start,
            Transaction.transaction_date < month_end,
        )
        .group_by(Transaction.category)
        .all()
    )

    spending_map: dict[str, Decimal] = {}
    for row in spending_query:
        category_name = row[0]
        total_spent = Decimal(str(row[1])) if row[1] else Decimal("0.00")
        spending_map[category_name] = total_spent

    result = []
    for budget in budgets:
        category_rel = budget.category
        category_name = ""
        if category_rel and hasattr(category_rel, "name"):
            category_name = category_rel.name
        else:
            category_name = str(budget.category_id)

        amount = Decimal(str(budget.amount))
        spent = spending_map.get(category_name, Decimal("0.00"))
        remaining = amount - spent

        result.append({
            "id": budget.id,
            "user_id": budget.user_id,
            "category_id": budget.category_id,
            "category": category_name,
            "month": budget.month,
            "amount": float(amount),
            "spent": float(spent),
            "remaining": float(remaining),
            "period": period,
            "description": "",
            "created_at": budget.created_at,
            "updated_at": budget.created_at,
        })

    return result


def set_budget(
    db: Session,
    user_id: str,
    category_name: str,
    amount: float,
    month: str,
    period: str = "monthly",
    description: Optional[str] = None,
) -> dict:
    """
    Create or update a budget for a user/category/month combination.
    If a budget already exists for the given user, category, and month, update it.
    Otherwise, create a new one.
    """
    category = (
        db.query(Category)
        .filter(
            Category.name == category_name,
            (Category.user_id == user_id) | (Category.user_id.is_(None)),
        )
        .first()
    )

    category_id = None
    if category:
        category_id = category.id
    else:
        category_id = None

    existing_budget = None
    if category_id:
        existing_budget = (
            db.query(Budget)
            .filter(
                Budget.user_id == user_id,
                Budget.category_id == category_id,
                Budget.month == month,
            )
            .first()
        )

    if existing_budget:
        existing_budget.amount = amount
        db.commit()
        db.refresh(existing_budget)

        return {
            "id": existing_budget.id,
            "user_id": existing_budget.user_id,
            "category_id": existing_budget.category_id,
            "category": category_name,
            "month": existing_budget.month,
            "amount": float(existing_budget.amount),
            "period": period,
            "description": description or "",
            "created_at": existing_budget.created_at,
            "updated_at": existing_budget.created_at,
        }
    else:
        if not category_id:
            new_category = Category(
                id=generate_uuid(),
                name=category_name,
                type="expense",
                is_system=False,
                user_id=user_id,
                created_at=datetime.utcnow(),
            )
            db.add(new_category)
            db.flush()
            category_id = new_category.id

        new_budget = Budget(
            id=generate_uuid(),
            user_id=user_id,
            category_id=category_id,
            month=month,
            amount=amount,
            created_at=datetime.utcnow(),
        )
        db.add(new_budget)
        db.commit()
        db.refresh(new_budget)

        return {
            "id": new_budget.id,
            "user_id": new_budget.user_id,
            "category_id": new_budget.category_id,
            "category": category_name,
            "month": new_budget.month,
            "amount": float(new_budget.amount),
            "period": period,
            "description": description or "",
            "created_at": new_budget.created_at,
            "updated_at": new_budget.created_at,
        }


def check_overspend(
    db: Session,
    user_id: str,
    month: str,
    threshold_percentage: float = 80.0,
) -> list[dict]:
    """
    Compare budget vs actual spending for a given month.
    Returns a list of alerts for budgets that are at or above the threshold percentage.
    """
    budgets_data = get_budgets_for_month(db, user_id, month)

    alerts = []
    for budget in budgets_data:
        amount = budget["amount"]
        spent = budget["spent"]

        if amount <= 0:
            continue

        percentage = (spent / amount) * 100.0

        if percentage >= threshold_percentage:
            alerts.append({
                "id": budget["id"],
                "category": budget["category"],
                "category_id": budget["category_id"],
                "amount": amount,
                "spent": spent,
                "remaining": budget["remaining"],
                "percentage": round(percentage, 1),
                "is_over": spent > amount,
            })

    alerts.sort(key=lambda x: x["percentage"], reverse=True)
    return alerts


def bulk_save_budgets(
    db: Session,
    user_id: str,
    budget_ids: list[str],
    amounts: list[float],
) -> int:
    """
    Bulk update budget amounts for a list of budget IDs.
    Only updates budgets that belong to the given user.
    Returns the number of budgets updated.
    """
    if len(budget_ids) != len(amounts):
        raise ValueError("budget_ids and amounts must have the same length")

    updated_count = 0

    for budget_id, new_amount in zip(budget_ids, amounts):
        if new_amount <= 0:
            continue

        budget = (
            db.query(Budget)
            .filter(
                Budget.id == budget_id,
                Budget.user_id == user_id,
            )
            .first()
        )

        if budget:
            budget.amount = new_amount
            updated_count += 1

    if updated_count > 0:
        db.commit()

    return updated_count


def delete_budget(
    db: Session,
    user_id: str,
    budget_id: str,
) -> bool:
    """
    Delete a budget by ID, ensuring it belongs to the given user.
    Returns True if deleted, False if not found.
    """
    budget = (
        db.query(Budget)
        .filter(
            Budget.id == budget_id,
            Budget.user_id == user_id,
        )
        .first()
    )

    if not budget:
        return False

    db.delete(budget)
    db.commit()
    return True


def get_budget_by_id(
    db: Session,
    user_id: str,
    budget_id: str,
) -> Optional[dict]:
    """
    Retrieve a single budget by ID for a given user.
    Returns a dict with budget info or None if not found.
    """
    budget = (
        db.query(Budget)
        .filter(
            Budget.id == budget_id,
            Budget.user_id == user_id,
        )
        .first()
    )

    if not budget:
        return None

    category_rel = budget.category
    category_name = ""
    if category_rel and hasattr(category_rel, "name"):
        category_name = category_rel.name
    else:
        category_name = str(budget.category_id)

    return {
        "id": budget.id,
        "user_id": budget.user_id,
        "category_id": budget.category_id,
        "category": category_name,
        "month": budget.month,
        "amount": float(budget.amount),
        "period": "monthly",
        "description": "",
        "created_at": budget.created_at,
        "updated_at": budget.created_at,
    }


def get_budget_summary(
    db: Session,
    user_id: str,
    month: str,
) -> dict:
    """
    Get summary totals for budgets in a given month.
    Returns total_budgeted, total_spent, total_remaining.
    """
    budgets_data = get_budgets_for_month(db, user_id, month)

    total_budgeted = sum(b["amount"] for b in budgets_data)
    total_spent = sum(b["spent"] for b in budgets_data)
    total_remaining = total_budgeted - total_spent

    return {
        "total_budgeted": round(total_budgeted, 2),
        "total_spent": round(total_spent, 2),
        "total_remaining": round(total_remaining, 2),
        "budget_count": len(budgets_data),
    }