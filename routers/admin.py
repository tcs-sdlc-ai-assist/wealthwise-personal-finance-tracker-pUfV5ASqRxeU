import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from services.auth_service import get_all_users, delete_user, activate_user, deactivate_user
from services.category_service import (
    get_system_categories_with_transaction_counts,
    create_system_category,
    update_system_category,
    delete_system_category,
)
from services.dashboard_service import get_admin_stats
from utils.dependencies import require_admin, render_template, set_flash_message

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/dashboard")
def admin_dashboard(
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stats = get_admin_stats(db)
    users = get_all_users(db)
    categories = get_system_categories_with_transaction_counts(db)

    return render_template(
        request,
        "admin/dashboard.html",
        user=user,
        stats=stats,
        users=users,
        categories=categories,
    )


@router.post("/admin/users/{user_id}/activate")
def admin_activate_user(
    request: Request,
    user_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target_user = activate_user(db, user_id)
    response = RedirectResponse(url="/admin/dashboard", status_code=303)
    if target_user:
        set_flash_message(response, "success", f"User '{target_user.username}' has been activated.")
    else:
        set_flash_message(response, "error", "User not found.")
    return response


@router.post("/admin/users/{user_id}/deactivate")
def admin_deactivate_user(
    request: Request,
    user_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == user.id:
        response = RedirectResponse(url="/admin/dashboard", status_code=303)
        set_flash_message(response, "error", "You cannot deactivate your own account.")
        return response

    target_user = deactivate_user(db, user_id)
    response = RedirectResponse(url="/admin/dashboard", status_code=303)
    if target_user:
        set_flash_message(response, "success", f"User '{target_user.username}' has been deactivated.")
    else:
        set_flash_message(response, "error", "User not found.")
    return response


@router.post("/admin/users/{user_id}/delete")
def admin_delete_user(
    request: Request,
    user_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == user.id:
        response = RedirectResponse(url="/admin/dashboard", status_code=303)
        set_flash_message(response, "error", "You cannot delete your own account.")
        return response

    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user and target_user.role == "admin":
        response = RedirectResponse(url="/admin/dashboard", status_code=303)
        set_flash_message(response, "error", "Cannot delete another admin user.")
        return response

    deleted = delete_user(db, user_id)
    response = RedirectResponse(url="/admin/dashboard", status_code=303)
    if deleted:
        set_flash_message(response, "success", "User has been permanently deleted.")
    else:
        set_flash_message(response, "error", "User not found.")
    return response


@router.post("/admin/categories/create")
def admin_create_category(
    request: Request,
    name: str = Form(...),
    description: Optional[str] = Form(""),
    color: Optional[str] = Form(""),
    icon: Optional[str] = Form(""),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    response = RedirectResponse(url="/admin/dashboard", status_code=303)

    name = name.strip()
    if not name:
        set_flash_message(response, "error", "Category name is required.")
        return response

    color_val = color.strip() if color else None
    if color_val and (not color_val.startswith("#") or len(color_val) != 7):
        color_val = None

    icon_val = icon.strip() if icon else None
    description_val = description.strip() if description else None

    try:
        create_system_category(
            db,
            name=name,
            description=description_val,
            color=color_val,
            icon=icon_val,
            is_active=True,
        )
        set_flash_message(response, "success", f"System category '{name}' created successfully.")
    except ValueError as e:
        set_flash_message(response, "error", str(e))
    except Exception:
        logger.exception("Error creating system category")
        set_flash_message(response, "error", "An unexpected error occurred while creating the category.")

    return response


@router.post("/admin/categories/{category_id}/edit")
def admin_edit_category(
    request: Request,
    category_id: str,
    name: str = Form(...),
    description: Optional[str] = Form(""),
    color: Optional[str] = Form(""),
    icon: Optional[str] = Form(""),
    is_active: Optional[str] = Form(""),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    response = RedirectResponse(url="/admin/dashboard", status_code=303)

    name = name.strip()
    if not name:
        set_flash_message(response, "error", "Category name is required.")
        return response

    color_val = color.strip() if color else None
    if color_val and (not color_val.startswith("#") or len(color_val) != 7):
        color_val = None

    icon_val = icon.strip() if icon else None
    description_val = description.strip() if description else None
    active = is_active in ("true", "on", "True", "1")

    try:
        updated = update_system_category(
            db,
            category_id=category_id,
            name=name,
            description=description_val,
            color=color_val,
            icon=icon_val,
            is_active=active,
        )
        if updated:
            set_flash_message(response, "success", f"Category '{name}' updated successfully.")
        else:
            set_flash_message(response, "error", "Category not found.")
    except ValueError as e:
        set_flash_message(response, "error", str(e))
    except Exception:
        logger.exception("Error updating system category")
        set_flash_message(response, "error", "An unexpected error occurred while updating the category.")

    return response


@router.post("/admin/categories/{category_id}/delete")
def admin_delete_category(
    request: Request,
    category_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    response = RedirectResponse(url="/admin/dashboard", status_code=303)

    try:
        deleted = delete_system_category(db, category_id)
        if deleted:
            set_flash_message(response, "success", "System category deleted successfully.")
        else:
            set_flash_message(response, "error", "Category not found.")
    except ValueError as e:
        set_flash_message(response, "error", str(e))
    except Exception:
        logger.exception("Error deleting system category")
        set_flash_message(response, "error", "An unexpected error occurred while deleting the category.")

    return response