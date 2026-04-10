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
from services.category_service import (
    get_categories_for_user,
    get_system_categories,
    get_custom_categories,
    get_categories_with_transaction_counts,
    create_category,
    update_category,
    delete_category,
    get_category_by_id,
    get_category_transaction_count,
)
from utils.dependencies import (
    require_auth,
    render_template,
    set_flash_message,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/categories")
def list_categories(
    request: Request,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    system_categories_raw = get_system_categories(db)
    system_categories = []
    for cat in system_categories_raw:
        count = get_category_transaction_count(db, cat.id)
        system_categories.append({
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

    custom_categories_raw = get_custom_categories(db, user.id)
    custom_categories = []
    for cat in custom_categories_raw:
        count = get_category_transaction_count(db, cat.id)
        custom_categories.append({
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

    return render_template(
        request,
        "categories/index.html",
        user=user,
        system_categories=system_categories,
        custom_categories=custom_categories,
    )


@router.post("/categories")
def create_category_route(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    color: str = Form(""),
    icon: str = Form(""),
    is_active: str = Form(""),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    color_value: Optional[str] = color.strip() if color and color.strip() else None
    icon_value: Optional[str] = icon.strip() if icon and icon.strip() else None
    description_value: Optional[str] = description.strip() if description and description.strip() else None
    is_active_value: bool = is_active.lower() in ("true", "on", "1", "yes") if is_active else True

    try:
        new_category = create_category(
            db=db,
            user_id=user.id,
            name=name.strip(),
            description=description_value,
            color=color_value,
            icon=icon_value,
            is_active=is_active_value,
        )
        response = RedirectResponse(url="/categories", status_code=303)
        set_flash_message(response, "success", f"Category '{new_category.name}' created successfully.")
        return response
    except ValueError as e:
        response = RedirectResponse(url="/categories", status_code=303)
        set_flash_message(response, "error", str(e))
        return response
    except Exception as e:
        logger.exception("Error creating category: %s", str(e))
        response = RedirectResponse(url="/categories", status_code=303)
        set_flash_message(response, "error", "An unexpected error occurred while creating the category.")
        return response


@router.post("/categories/{category_id}/edit")
def edit_category_route(
    request: Request,
    category_id: str,
    name: str = Form(...),
    description: str = Form(""),
    color: str = Form(""),
    icon: str = Form(""),
    is_active: str = Form(""),
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    color_value: Optional[str] = color.strip() if color and color.strip() else None
    icon_value: Optional[str] = icon.strip() if icon and icon.strip() else None
    description_value: Optional[str] = description.strip() if description and description.strip() else None
    is_active_value: Optional[bool] = is_active.lower() in ("true", "on", "1", "yes") if is_active else None

    try:
        updated_category = update_category(
            db=db,
            category_id=category_id,
            user_id=user.id,
            name=name.strip() if name and name.strip() else None,
            description=description_value,
            color=color_value,
            icon=icon_value,
            is_active=is_active_value,
        )
        if updated_category is None:
            response = RedirectResponse(url="/categories", status_code=303)
            set_flash_message(response, "error", "Category not found.")
            return response

        response = RedirectResponse(url="/categories", status_code=303)
        set_flash_message(response, "success", f"Category '{updated_category.name}' updated successfully.")
        return response
    except ValueError as e:
        response = RedirectResponse(url="/categories", status_code=303)
        set_flash_message(response, "error", str(e))
        return response
    except PermissionError as e:
        response = RedirectResponse(url="/categories", status_code=303)
        set_flash_message(response, "error", str(e))
        return response
    except Exception as e:
        logger.exception("Error updating category %s: %s", category_id, str(e))
        response = RedirectResponse(url="/categories", status_code=303)
        set_flash_message(response, "error", "An unexpected error occurred while updating the category.")
        return response


@router.post("/categories/{category_id}/delete")
def delete_category_route(
    request: Request,
    category_id: str,
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    category = get_category_by_id(db, category_id)
    category_name = category.name if category else "Unknown"

    try:
        deleted = delete_category(
            db=db,
            category_id=category_id,
            user_id=user.id,
        )
        if not deleted:
            response = RedirectResponse(url="/categories", status_code=303)
            set_flash_message(response, "error", "Category not found.")
            return response

        response = RedirectResponse(url="/categories", status_code=303)
        set_flash_message(response, "success", f"Category '{category_name}' deleted successfully. Transactions reassigned to 'Other'.")
        return response
    except ValueError as e:
        response = RedirectResponse(url="/categories", status_code=303)
        set_flash_message(response, "error", str(e))
        return response
    except PermissionError as e:
        response = RedirectResponse(url="/categories", status_code=303)
        set_flash_message(response, "error", str(e))
        return response
    except Exception as e:
        logger.exception("Error deleting category %s: %s", category_id, str(e))
        response = RedirectResponse(url="/categories", status_code=303)
        set_flash_message(response, "error", "An unexpected error occurred while deleting the category.")
        return response