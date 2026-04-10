import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from services.budget_service import (
    delete_budget,
    get_budget_summary,
    get_budgets_for_month,
    set_budget,
    bulk_save_budgets,
)
from services.category_service import get_categories_for_user
from utils.dependencies import (
    render_template,
    require_auth,
    set_flash_message,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/budgets")
def list_budgets(
    request: Request,
    month: Optional[str] = Query(None),
    period: Optional[str] = Query("monthly"),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    if not month:
        today = date.today()
        month = f"{today.year:04d}-{today.month:02d}"

    if period not in ("monthly", "weekly", "yearly"):
        period = "monthly"

    budgets = get_budgets_for_month(db, user.id, month, period=period)
    summary = get_budget_summary(db, user.id, month)

    return render_template(
        request,
        "budgets/index.html",
        user=user,
        budgets=budgets,
        selected_month=month,
        selected_period=period,
        total_budgeted=summary.get("total_budgeted", 0),
        total_spent=summary.get("total_spent", 0),
        total_remaining=summary.get("total_remaining", 0),
    )


@router.get("/budgets/create")
def create_budget_form(
    request: Request,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    categories = get_categories_for_user(db, user.id)
    today = date.today()
    default_month = f"{today.year:04d}-{today.month:02d}"

    return render_template(
        request,
        "budgets/create.html",
        user=user,
        categories=categories,
        default_month=default_month,
    )


@router.post("/budgets/create")
def create_budget(
    request: Request,
    category: str = Form(...),
    amount: float = Form(...),
    month: str = Form(...),
    period: str = Form("monthly"),
    description: str = Form(""),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        if amount <= 0:
            response = RedirectResponse(url="/budgets/create", status_code=303)
            set_flash_message(response, "error", "Budget amount must be greater than zero.")
            return response

        set_budget(
            db=db,
            user_id=user.id,
            category_name=category,
            amount=amount,
            month=month,
            period=period,
            description=description if description else None,
        )

        response = RedirectResponse(url=f"/budgets?month={month}&period={period}", status_code=303)
        set_flash_message(response, "success", f"Budget for '{category}' saved successfully.")
        return response
    except Exception as e:
        logger.exception("Error creating budget: %s", str(e))
        response = RedirectResponse(url="/budgets/create", status_code=303)
        set_flash_message(response, "error", f"Failed to create budget: {str(e)}")
        return response


@router.post("/budgets/bulk-save")
def bulk_save(
    request: Request,
    budget_ids: list[str] = Form(...),
    amounts: list[float] = Form(...),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        updated_count = bulk_save_budgets(
            db=db,
            user_id=user.id,
            budget_ids=budget_ids,
            amounts=amounts,
        )

        response = RedirectResponse(url="/budgets", status_code=303)
        set_flash_message(
            response,
            "success",
            f"Successfully updated {updated_count} budget{'s' if updated_count != 1 else ''}.",
        )
        return response
    except ValueError as e:
        logger.warning("Bulk save validation error: %s", str(e))
        response = RedirectResponse(url="/budgets", status_code=303)
        set_flash_message(response, "error", f"Validation error: {str(e)}")
        return response
    except Exception as e:
        logger.exception("Error during bulk save: %s", str(e))
        response = RedirectResponse(url="/budgets", status_code=303)
        set_flash_message(response, "error", "Failed to save budget changes.")
        return response


@router.get("/budgets/{budget_id}/edit")
def edit_budget_form(
    request: Request,
    budget_id: str,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    from services.budget_service import get_budget_by_id

    budget = get_budget_by_id(db, user.id, budget_id)
    if budget is None:
        response = RedirectResponse(url="/budgets", status_code=303)
        set_flash_message(response, "error", "Budget not found.")
        return response

    categories = get_categories_for_user(db, user.id)

    return render_template(
        request,
        "budgets/edit.html",
        user=user,
        budget=budget,
        categories=categories,
    )


@router.post("/budgets/{budget_id}/edit")
def update_budget(
    request: Request,
    budget_id: str,
    category: str = Form(...),
    amount: float = Form(...),
    month: str = Form(...),
    period: str = Form("monthly"),
    description: str = Form(""),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    try:
        if amount <= 0:
            response = RedirectResponse(url=f"/budgets/{budget_id}/edit", status_code=303)
            set_flash_message(response, "error", "Budget amount must be greater than zero.")
            return response

        set_budget(
            db=db,
            user_id=user.id,
            category_name=category,
            amount=amount,
            month=month,
            period=period,
            description=description if description else None,
        )

        response = RedirectResponse(url=f"/budgets?month={month}&period={period}", status_code=303)
        set_flash_message(response, "success", f"Budget for '{category}' updated successfully.")
        return response
    except Exception as e:
        logger.exception("Error updating budget %s: %s", budget_id, str(e))
        response = RedirectResponse(url=f"/budgets/{budget_id}/edit", status_code=303)
        set_flash_message(response, "error", f"Failed to update budget: {str(e)}")
        return response


@router.post("/budgets/{budget_id}/delete")
def delete_budget_route(
    request: Request,
    budget_id: str,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    deleted = delete_budget(db, user.id, budget_id)

    if deleted:
        response = RedirectResponse(url="/budgets", status_code=303)
        set_flash_message(response, "success", "Budget deleted successfully.")
    else:
        response = RedirectResponse(url="/budgets", status_code=303)
        set_flash_message(response, "error", "Budget not found or could not be deleted.")

    return response