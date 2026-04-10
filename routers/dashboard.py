import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from services.dashboard_service import (
    get_admin_stats,
    get_category_breakdown,
    get_dashboard_summary,
    get_recent_transactions,
)
from utils.dependencies import (
    get_flash_messages,
    clear_flash_messages,
    render_template,
    require_auth,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dashboard")
def dashboard_page(
    request: Request,
    month: Optional[str] = None,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """
    Render the main user dashboard with summary cards, category breakdown,
    recent transactions, and budget alerts for the selected month.
    """
    today = date.today()

    if month:
        try:
            parts = month.split("-")
            year_int = int(parts[0])
            month_int = int(parts[1])
            if not (1 <= month_int <= 12):
                raise ValueError("Invalid month")
            selected_month = f"{year_int:04d}-{month_int:02d}"
        except (ValueError, IndexError):
            selected_month = f"{today.year:04d}-{today.month:02d}"
    else:
        selected_month = f"{today.year:04d}-{today.month:02d}"

    try:
        summary = get_dashboard_summary(db, user.id, month=selected_month)
    except Exception:
        logger.exception("Error fetching dashboard summary for user %s", user.id)
        summary = {
            "total_income": 0.0,
            "total_expenses": 0.0,
            "net_savings": 0.0,
            "income_change": None,
            "expense_change": None,
            "budget_alerts": [],
            "selected_month": selected_month,
        }

    try:
        category_breakdown = get_category_breakdown(db, user.id, month=selected_month)
    except Exception:
        logger.exception("Error fetching category breakdown for user %s", user.id)
        category_breakdown = []

    try:
        recent_transactions = get_recent_transactions(db, user.id, limit=10)
    except Exception:
        logger.exception("Error fetching recent transactions for user %s", user.id)
        recent_transactions = []

    total_income = summary.get("total_income", 0.0)
    total_expenses = summary.get("total_expenses", 0.0)
    net_savings = summary.get("net_savings", 0.0)
    income_change = summary.get("income_change")
    expense_change = summary.get("expense_change")
    budget_alerts = summary.get("budget_alerts", [])

    return render_template(
        request=request,
        template_name="dashboard/index.html",
        user=user,
        selected_month=selected_month,
        total_income=total_income,
        total_expenses=total_expenses,
        net_savings=net_savings,
        income_change=income_change,
        expense_change=expense_change,
        budget_alerts=budget_alerts,
        category_breakdown=category_breakdown,
        recent_transactions=recent_transactions,
    )