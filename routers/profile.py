import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_db
from models.category import Category
from models.transaction import Transaction
from models.user import User
from services.auth_service import change_password, update_user_profile
from utils.dependencies import (
    render_template,
    require_auth,
    set_flash_message,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/profile")
def profile_page(
    request: Request,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    total_transactions = db.execute(
        select(func.count(Transaction.id)).where(Transaction.user_id == user.id)
    ).scalar() or 0

    total_categories = db.execute(
        select(func.count(Category.id)).where(
            (Category.user_id == user.id) | (Category.is_system == True)
        )
    ).scalar() or 0

    member_since = ""
    if user.created_at:
        member_since = user.created_at.strftime("%b %d, %Y")

    return render_template(
        request,
        "profile/index.html",
        user=user,
        total_transactions=total_transactions,
        total_categories=total_categories,
        member_since=member_since,
    )


@router.post("/profile/update")
def update_profile(
    request: Request,
    username: str = Form(""),
    email: str = Form(""),
    full_name: str = Form(""),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    username = username.strip() if username else None
    email = email.strip() if email else None
    full_name = full_name.strip() if full_name else None

    try:
        updated_user = update_user_profile(
            db=db,
            user_id=user.id,
            username=username if username else None,
            email=email if email else None,
            full_name=full_name,
        )

        if updated_user is None:
            response = RedirectResponse(url="/profile", status_code=303)
            set_flash_message(response, "error", "User not found.")
            return response

        response = RedirectResponse(url="/profile", status_code=303)
        set_flash_message(response, "success", "Profile updated successfully.")
        return response

    except ValueError as e:
        response = RedirectResponse(url="/profile", status_code=303)
        set_flash_message(response, "error", str(e))
        return response
    except Exception as e:
        logger.exception("Error updating profile for user %s: %s", user.id, e)
        response = RedirectResponse(url="/profile", status_code=303)
        set_flash_message(response, "error", "An unexpected error occurred while updating your profile.")
        return response


@router.post("/profile/change-password")
def change_user_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    if new_password != confirm_password:
        response = RedirectResponse(url="/profile", status_code=303)
        set_flash_message(response, "error", "New password and confirmation do not match.")
        return response

    if len(new_password) < 8:
        response = RedirectResponse(url="/profile", status_code=303)
        set_flash_message(response, "error", "Password must be at least 8 characters long.")
        return response

    if not any(c.isupper() for c in new_password):
        response = RedirectResponse(url="/profile", status_code=303)
        set_flash_message(response, "error", "Password must contain at least one uppercase letter.")
        return response

    if not any(c.islower() for c in new_password):
        response = RedirectResponse(url="/profile", status_code=303)
        set_flash_message(response, "error", "Password must contain at least one lowercase letter.")
        return response

    if not any(c.isdigit() for c in new_password):
        response = RedirectResponse(url="/profile", status_code=303)
        set_flash_message(response, "error", "Password must contain at least one digit.")
        return response

    try:
        result = change_password(
            db=db,
            user_id=user.id,
            current_password=current_password,
            new_password=new_password,
        )

        if not result:
            response = RedirectResponse(url="/profile", status_code=303)
            set_flash_message(response, "error", "Failed to change password.")
            return response

        response = RedirectResponse(url="/profile", status_code=303)
        set_flash_message(response, "success", "Password changed successfully.")
        return response

    except ValueError as e:
        response = RedirectResponse(url="/profile", status_code=303)
        set_flash_message(response, "error", str(e))
        return response
    except Exception as e:
        logger.exception("Error changing password for user %s: %s", user.id, e)
        response = RedirectResponse(url="/profile", status_code=303)
        set_flash_message(response, "error", "An unexpected error occurred while changing your password.")
        return response