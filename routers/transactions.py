import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from services.transaction_service import (
    create_transaction,
    delete_transaction,
    export_transactions_csv,
    get_distinct_categories,
    get_transaction_by_id,
    get_transaction_summary,
    get_transactions,
    update_transaction,
)
from services.category_service import get_categories_for_user
from utils.dependencies import (
    render_template,
    require_auth,
    set_flash_message,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/transactions")
def list_transactions(
    request: Request,
    page: int = Query(1, ge=1),
    type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    parsed_date_from: Optional[date] = None
    parsed_date_to: Optional[date] = None

    if date_from:
        try:
            parsed_date_from = date.fromisoformat(date_from)
        except (ValueError, TypeError):
            parsed_date_from = None

    if date_to:
        try:
            parsed_date_to = date.fromisoformat(date_to)
        except (ValueError, TypeError):
            parsed_date_to = None

    per_page = 50

    result = get_transactions(
        db=db,
        user_id=user.id,
        type=type if type else None,
        category=category if category else None,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        page=page,
        per_page=per_page,
        sort_by="transaction_date",
        sort_order="desc",
    )

    summary = get_transaction_summary(
        db=db,
        user_id=user.id,
        type=type if type else None,
        category=category if category else None,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
    )

    categories_list = get_distinct_categories(db=db, user_id=user.id)

    filters = {
        "type": type or "",
        "category": category or "",
        "date_from": date_from or "",
        "date_to": date_to or "",
    }

    return render_template(
        request=request,
        template_name="transactions/list.html",
        user=user,
        transactions=result["transactions"],
        total_count=result["total_count"],
        current_page=result["page"],
        total_pages=result["total_pages"],
        per_page=result["per_page"],
        total_income=summary["total_income"],
        total_expenses=summary["total_expenses"],
        net_balance=summary["net_balance"],
        categories=categories_list,
        filters=filters,
    )


@router.get("/transactions/export/csv")
def export_csv(
    request: Request,
    type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    parsed_date_from: Optional[date] = None
    parsed_date_to: Optional[date] = None

    if date_from:
        try:
            parsed_date_from = date.fromisoformat(date_from)
        except (ValueError, TypeError):
            parsed_date_from = None

    if date_to:
        try:
            parsed_date_to = date.fromisoformat(date_to)
        except (ValueError, TypeError):
            parsed_date_to = None

    csv_content = export_transactions_csv(
        db=db,
        user_id=user.id,
        type=type if type else None,
        category=category if category else None,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
    )

    today_str = date.today().isoformat()
    filename = f"wealthwise_transactions_{today_str}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/transactions/new")
def new_transaction_form(
    request: Request,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    categories = get_categories_for_user(db=db, user_id=user.id)
    today_str = date.today().isoformat()

    return render_template(
        request=request,
        template_name="transactions/form.html",
        user=user,
        transaction=None,
        categories=categories,
        today=today_str,
    )


@router.post("/transactions/create")
def create_transaction_handler(
    request: Request,
    type: str = Form(...),
    category: str = Form(...),
    amount: str = Form(...),
    transaction_date: str = Form(...),
    description: str = Form(""),
    account_id: str = Form(""),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    errors = []

    if not type or type not in ("income", "expense", "transfer"):
        errors.append("Invalid transaction type. Must be income, expense, or transfer.")

    if not category or not category.strip():
        errors.append("Category is required.")

    parsed_amount: Optional[Decimal] = None
    if not amount:
        errors.append("Amount is required.")
    else:
        try:
            parsed_amount = Decimal(amount)
            if parsed_amount <= 0:
                errors.append("Amount must be greater than zero.")
        except (InvalidOperation, ValueError):
            errors.append("Invalid amount value.")

    parsed_date: Optional[date] = None
    if not transaction_date:
        errors.append("Transaction date is required.")
    else:
        try:
            parsed_date = date.fromisoformat(transaction_date)
        except (ValueError, TypeError):
            errors.append("Invalid date format.")

    if errors:
        categories = get_categories_for_user(db=db, user_id=user.id)
        today_str = date.today().isoformat()
        response = render_template(
            request=request,
            template_name="transactions/form.html",
            user=user,
            transaction=None,
            categories=categories,
            today=today_str,
            status_code=422,
        )
        set_flash_message(response, "error", " ".join(errors))
        return response

    try:
        create_transaction(
            db=db,
            user_id=user.id,
            amount=parsed_amount,
            type=type,
            category=category.strip(),
            description=description.strip() if description else None,
            transaction_date=parsed_date,
            account_id=account_id.strip() if account_id and account_id.strip() else None,
        )

        response = RedirectResponse(url="/transactions", status_code=303)
        set_flash_message(response, "success", "Transaction created successfully.")
        return response

    except Exception as e:
        logger.exception("Error creating transaction: %s", str(e))
        categories = get_categories_for_user(db=db, user_id=user.id)
        today_str = date.today().isoformat()
        response = render_template(
            request=request,
            template_name="transactions/form.html",
            user=user,
            transaction=None,
            categories=categories,
            today=today_str,
            status_code=500,
        )
        set_flash_message(response, "error", "An error occurred while creating the transaction.")
        return response


@router.get("/transactions/{transaction_id}/edit")
def edit_transaction_form(
    request: Request,
    transaction_id: str,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    transaction = get_transaction_by_id(db=db, transaction_id=transaction_id, user_id=user.id)

    if transaction is None:
        response = RedirectResponse(url="/transactions", status_code=303)
        set_flash_message(response, "error", "Transaction not found.")
        return response

    categories = get_categories_for_user(db=db, user_id=user.id)
    today_str = date.today().isoformat()

    return render_template(
        request=request,
        template_name="transactions/form.html",
        user=user,
        transaction=transaction,
        categories=categories,
        today=today_str,
    )


@router.post("/transactions/{transaction_id}/edit")
def update_transaction_handler(
    request: Request,
    transaction_id: str,
    type: str = Form(...),
    category: str = Form(...),
    amount: str = Form(...),
    transaction_date: str = Form(...),
    description: str = Form(""),
    account_id: str = Form(""),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    existing_transaction = get_transaction_by_id(db=db, transaction_id=transaction_id, user_id=user.id)

    if existing_transaction is None:
        response = RedirectResponse(url="/transactions", status_code=303)
        set_flash_message(response, "error", "Transaction not found.")
        return response

    errors = []

    if not type or type not in ("income", "expense", "transfer"):
        errors.append("Invalid transaction type. Must be income, expense, or transfer.")

    if not category or not category.strip():
        errors.append("Category is required.")

    parsed_amount: Optional[Decimal] = None
    if not amount:
        errors.append("Amount is required.")
    else:
        try:
            parsed_amount = Decimal(amount)
            if parsed_amount <= 0:
                errors.append("Amount must be greater than zero.")
        except (InvalidOperation, ValueError):
            errors.append("Invalid amount value.")

    parsed_date: Optional[date] = None
    if not transaction_date:
        errors.append("Transaction date is required.")
    else:
        try:
            parsed_date = date.fromisoformat(transaction_date)
        except (ValueError, TypeError):
            errors.append("Invalid date format.")

    if errors:
        categories = get_categories_for_user(db=db, user_id=user.id)
        today_str = date.today().isoformat()
        response = render_template(
            request=request,
            template_name="transactions/form.html",
            user=user,
            transaction=existing_transaction,
            categories=categories,
            today=today_str,
            status_code=422,
        )
        set_flash_message(response, "error", " ".join(errors))
        return response

    try:
        updated = update_transaction(
            db=db,
            transaction_id=transaction_id,
            user_id=user.id,
            amount=parsed_amount,
            type=type,
            category=category.strip(),
            description=description.strip() if description else None,
            transaction_date=parsed_date,
            account_id=account_id.strip() if account_id and account_id.strip() else None,
        )

        if updated is None:
            response = RedirectResponse(url="/transactions", status_code=303)
            set_flash_message(response, "error", "Transaction not found or could not be updated.")
            return response

        response = RedirectResponse(url="/transactions", status_code=303)
        set_flash_message(response, "success", "Transaction updated successfully.")
        return response

    except Exception as e:
        logger.exception("Error updating transaction %s: %s", transaction_id, str(e))
        categories = get_categories_for_user(db=db, user_id=user.id)
        today_str = date.today().isoformat()
        response = render_template(
            request=request,
            template_name="transactions/form.html",
            user=user,
            transaction=existing_transaction,
            categories=categories,
            today=today_str,
            status_code=500,
        )
        set_flash_message(response, "error", "An error occurred while updating the transaction.")
        return response


@router.post("/transactions/{transaction_id}/delete")
def delete_transaction_handler(
    request: Request,
    transaction_id: str,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    deleted = delete_transaction(db=db, transaction_id=transaction_id, user_id=user.id)

    if not deleted:
        response = RedirectResponse(url="/transactions", status_code=303)
        set_flash_message(response, "error", "Transaction not found or could not be deleted.")
        return response

    response = RedirectResponse(url="/transactions", status_code=303)
    set_flash_message(response, "success", "Transaction deleted successfully.")
    return response