import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func, select, and_, extract
from sqlalchemy.orm import Session

from database import get_db
from models.budget import Budget
from models.category import Category
from models.transaction import Transaction
from models.user import User

logger = logging.getLogger(__name__)


def get_dashboard_summary(
    db: Session,
    user_id: str,
    month: Optional[str] = None,
) -> dict[str, Any]:
    """
    Get dashboard summary for a user for a given month.
    Returns total income, total expenses, net savings, budget alerts,
    and month-over-month change percentages.
    """
    if month:
        try:
            year, mon = month.split("-")
            year = int(year)
            mon = int(mon)
        except (ValueError, AttributeError):
            today = date.today()
            year = today.year
            mon = today.month
    else:
        today = date.today()
        year = today.year
        mon = today.month

    selected_month = f"{year:04d}-{mon:02d}"

    # Calculate total income for the selected month
    income_result = db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == "income",
                extract("year", Transaction.transaction_date) == year,
                extract("month", Transaction.transaction_date) == mon,
            )
        )
    ).scalar()
    total_income = float(income_result or 0)

    # Calculate total expenses for the selected month
    expense_result = db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == "expense",
                extract("year", Transaction.transaction_date) == year,
                extract("month", Transaction.transaction_date) == mon,
            )
        )
    ).scalar()
    total_expenses = float(expense_result or 0)

    # Calculate previous month totals for comparison
    if mon == 1:
        prev_year = year - 1
        prev_mon = 12
    else:
        prev_year = year
        prev_mon = mon - 1

    prev_income_result = db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == "income",
                extract("year", Transaction.transaction_date) == prev_year,
                extract("month", Transaction.transaction_date) == prev_mon,
            )
        )
    ).scalar()
    prev_income = float(prev_income_result or 0)

    prev_expense_result = db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == "expense",
                extract("year", Transaction.transaction_date) == prev_year,
                extract("month", Transaction.transaction_date) == prev_mon,
            )
        )
    ).scalar()
    prev_expenses = float(prev_expense_result or 0)

    # Calculate percentage changes
    income_change = None
    if prev_income > 0:
        income_change = ((total_income - prev_income) / prev_income) * 100
    elif total_income > 0:
        income_change = 100.0

    expense_change = None
    if prev_expenses > 0:
        expense_change = ((total_expenses - prev_expenses) / prev_expenses) * 100
    elif total_expenses > 0:
        expense_change = 100.0

    # Get budget alerts (budgets where spending >= 80%)
    budget_alerts = _get_budget_alerts(db, user_id, selected_month)

    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_savings": total_income - total_expenses,
        "income_change": income_change,
        "expense_change": expense_change,
        "budget_alerts": budget_alerts,
        "selected_month": selected_month,
    }


def _get_budget_alerts(
    db: Session,
    user_id: str,
    month: str,
) -> list[dict[str, Any]]:
    """
    Get budget alerts for budgets where spending is >= 80% of the budget amount.
    """
    alerts: list[dict[str, Any]] = []

    budgets = db.execute(
        select(Budget).where(
            and_(
                Budget.user_id == user_id,
                Budget.month == month,
            )
        )
    ).scalars().all()

    if not budgets:
        return alerts

    try:
        year, mon = month.split("-")
        year_int = int(year)
        mon_int = int(mon)
    except (ValueError, AttributeError):
        return alerts

    for budget in budgets:
        category = budget.category
        if category is None:
            continue

        category_name = category.name if category else None
        if not category_name:
            continue

        spent_result = db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.type == "expense",
                    Transaction.category == category_name,
                    extract("year", Transaction.transaction_date) == year_int,
                    extract("month", Transaction.transaction_date) == mon_int,
                )
            )
        ).scalar()
        spent = float(spent_result or 0)
        budget_amount = float(budget.amount or 0)

        if budget_amount > 0:
            percentage = (spent / budget_amount) * 100
        else:
            percentage = 0.0

        if percentage >= 80:
            alerts.append({
                "category": category_name,
                "amount": budget_amount,
                "spent": spent,
                "remaining": budget_amount - spent,
                "percentage": percentage,
            })

    alerts.sort(key=lambda a: a["percentage"], reverse=True)
    return alerts


def get_category_breakdown(
    db: Session,
    user_id: str,
    month: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Get spending breakdown by category for the selected month.
    Returns list of categories with amount and percentage of total spending.
    """
    if month:
        try:
            year, mon = month.split("-")
            year_int = int(year)
            mon_int = int(mon)
        except (ValueError, AttributeError):
            today = date.today()
            year_int = today.year
            mon_int = today.month
    else:
        today = date.today()
        year_int = today.year
        mon_int = today.month

    # Get expense totals grouped by category
    results = db.execute(
        select(
            Transaction.category,
            func.sum(Transaction.amount).label("total_amount"),
        ).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.type == "expense",
                extract("year", Transaction.transaction_date) == year_int,
                extract("month", Transaction.transaction_date) == mon_int,
            )
        ).group_by(Transaction.category).order_by(func.sum(Transaction.amount).desc())
    ).all()

    if not results:
        return []

    total_spending = sum(float(row.total_amount or 0) for row in results)

    breakdown: list[dict[str, Any]] = []
    for row in results:
        amount = float(row.total_amount or 0)
        percentage = (amount / total_spending * 100) if total_spending > 0 else 0.0

        # Try to find the category color
        cat = db.execute(
            select(Category).where(
                and_(
                    Category.name == row.category,
                    (
                        (Category.user_id == user_id) | (Category.is_system == True)
                    ),
                )
            )
        ).scalars().first()

        color = cat.color if cat and cat.color else None

        breakdown.append({
            "name": row.category,
            "amount": amount,
            "percentage": round(percentage, 1),
            "color": color,
        })

    return breakdown


def get_recent_transactions(
    db: Session,
    user_id: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Get the most recent transactions for a user.
    """
    transactions = db.execute(
        select(Transaction).where(
            Transaction.user_id == user_id,
        ).order_by(
            Transaction.transaction_date.desc(),
            Transaction.created_at.desc(),
        ).limit(limit)
    ).scalars().all()

    result: list[dict[str, Any]] = []
    for txn in transactions:
        result.append({
            "id": txn.id,
            "type": txn.type,
            "category": txn.category,
            "amount": float(txn.amount),
            "description": txn.description,
            "transaction_date": txn.transaction_date,
            "account_id": txn.account_id,
            "created_at": txn.created_at,
        })

    return result


def get_admin_stats(db: Session) -> dict[str, Any]:
    """
    Get system-wide statistics for the admin dashboard.
    Returns total users, active users, total transactions, and system value.
    """
    total_users = db.execute(
        select(func.count(User.id))
    ).scalar() or 0

    active_users = db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    ).scalar() or 0

    total_transactions = db.execute(
        select(func.count(Transaction.id))
    ).scalar() or 0

    # System value: total income minus total expenses across all users
    total_income = db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.type == "income"
        )
    ).scalar() or 0

    total_expenses = db.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.type == "expense"
        )
    ).scalar() or 0

    system_value = float(total_income) - float(total_expenses)

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_transactions": total_transactions,
        "system_value": system_value,
    }