import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from utils.security import verify_token

logger = logging.getLogger(__name__)

templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


def get_flash_messages(request: Request) -> list[dict]:
    """
    Retrieve flash messages from the session/cookies and clear them.
    Returns a list of dicts with 'type' and 'text' keys.
    """
    messages: list[dict] = []
    flash_cookie = request.cookies.get("flash_messages", "")
    if not flash_cookie:
        return messages

    try:
        import json
        raw_messages = json.loads(flash_cookie)
        if isinstance(raw_messages, list):
            for msg in raw_messages:
                if isinstance(msg, dict) and "type" in msg and "text" in msg:
                    messages.append({
                        "type": str(msg["type"]),
                        "text": str(msg["text"]),
                    })
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning("Failed to parse flash messages cookie")

    return messages


def set_flash_message(response, message_type: str, text: str) -> None:
    """
    Set a flash message cookie on the response.
    message_type should be one of: 'success', 'error', 'warning', 'info'.
    """
    import json
    messages = [{"type": message_type, "text": text}]
    response.set_cookie(
        key="flash_messages",
        value=json.dumps(messages),
        max_age=60,
        httponly=True,
        samesite="lax",
    )


def clear_flash_messages(response) -> None:
    """Remove flash messages cookie from the response."""
    response.delete_cookie(key="flash_messages")


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Get the current user from the access_token cookie if present.
    Returns None if not authenticated (does not raise).
    """
    token = request.cookies.get("access_token")
    if not token:
        return None

    payload = verify_token(token)
    if payload is None:
        return None

    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return None

    if not user.is_active:
        return None

    return user


def require_auth(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency that requires authentication.
    Redirects to /auth/login if the user is not authenticated.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/login"},
        )

    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/login"},
        )

    user_id: Optional[str] = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/login"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/login"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/auth/login"},
        )

    return user


def require_admin(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency that requires admin role.
    Redirects to /auth/login if not authenticated.
    Redirects to /dashboard if authenticated but not admin.
    """
    user = require_auth(request=request, db=db)

    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/dashboard"},
        )

    return user


def get_template_context(
    request: Request,
    user: Optional[User] = None,
    **kwargs,
) -> dict:
    """
    Build a standard template context dict with common variables.
    Includes user, current_year, messages, and any additional kwargs.
    """
    messages = get_flash_messages(request)
    now = datetime.now(timezone.utc)

    context = {
        "user": user,
        "current_year": now.year,
        "messages": messages,
    }
    context.update(kwargs)

    return context


def render_template(
    request: Request,
    template_name: str,
    user: Optional[User] = None,
    status_code: int = 200,
    **kwargs,
):
    """
    Render a Jinja2 template with standard context.
    Automatically includes user, current_year, and flash messages.
    Returns a TemplateResponse with flash messages cookie cleared.
    """
    context = get_template_context(request=request, user=user, **kwargs)

    response = templates.TemplateResponse(
        request,
        template_name,
        context=context,
        status_code=status_code,
    )

    if get_flash_messages(request):
        clear_flash_messages(response)

    return response