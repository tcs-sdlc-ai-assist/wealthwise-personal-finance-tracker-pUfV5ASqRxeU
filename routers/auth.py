import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
from services.auth_service import (
    authenticate_user,
    create_user_access_token,
    register_user,
)
from utils.dependencies import (
    get_current_user_optional,
    render_template,
    set_flash_message,
)
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/register")
def register_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=303)

    return render_template(
        request=request,
        template_name="auth/register.html",
        user=None,
        error=None,
        errors=None,
        form_data=None,
    )


@router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    display_name: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=303)

    form_data = {
        "email": email,
        "username": username,
        "display_name": display_name,
    }

    errors: list[str] = []

    username = username.strip()
    email = email.strip().lower()
    display_name = display_name.strip() if display_name else ""

    if len(username) < 3:
        errors.append("Username must be at least 3 characters long.")
    if len(username) > 50:
        errors.append("Username must be at most 50 characters long.")
    if username and not all(c.isalnum() or c in ("_", "-") for c in username):
        errors.append("Username must contain only alphanumeric characters, underscores, or hyphens.")

    if not email:
        errors.append("Email address is required.")

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    elif len(password) > 128:
        errors.append("Password must be at most 128 characters long.")
    else:
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit.")

    if password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        return render_template(
            request=request,
            template_name="auth/register.html",
            user=None,
            errors=errors,
            error=None,
            form_data=form_data,
        )

    try:
        full_name = display_name if display_name else None
        user = register_user(
            db=db,
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            role="user",
        )
        logger.info("New user registered: %s (id=%s)", user.username, user.id)
    except ValueError as e:
        return render_template(
            request=request,
            template_name="auth/register.html",
            user=None,
            error=str(e),
            errors=None,
            form_data=form_data,
        )
    except Exception:
        logger.exception("Unexpected error during registration")
        return render_template(
            request=request,
            template_name="auth/register.html",
            user=None,
            error="An unexpected error occurred. Please try again.",
            errors=None,
            form_data=form_data,
        )

    response = RedirectResponse(url="/auth/login", status_code=303)
    set_flash_message(response, "success", "Account created successfully! Please sign in.")
    return response


@router.get("/login")
def login_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=303)

    return render_template(
        request=request,
        template_name="auth/login.html",
        user=None,
        email=None,
    )


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    remember_me: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional),
):
    if current_user is not None:
        return RedirectResponse(url="/dashboard", status_code=303)

    email = email.strip().lower()

    user = authenticate_user(db=db, email=email, password=password)

    if user is None:
        logger.warning("Failed login attempt for email: %s", email)
        messages = [{"type": "error", "text": "Invalid email or password. Please try again."}]
        return render_template(
            request=request,
            template_name="auth/login.html",
            user=None,
            email=email,
            messages=messages,
        )

    access_token = create_user_access_token(user)

    response = RedirectResponse(url="/dashboard", status_code=303)

    max_age = 60 * 60 * 24 * 30 if remember_me else 60 * 60 * 24
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
    )

    set_flash_message(response, "success", f"Welcome back, {user.full_name or user.username}!")
    logger.info("User '%s' (id=%s) logged in successfully", user.username, user.id)
    return response


@router.get("/logout")
def logout_get(request: Request):
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(key="access_token")
    set_flash_message(response, "info", "You have been signed out.")
    return response


@router.post("/logout")
def logout_post(request: Request):
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(key="access_token")
    set_flash_message(response, "info", "You have been signed out.")
    return response