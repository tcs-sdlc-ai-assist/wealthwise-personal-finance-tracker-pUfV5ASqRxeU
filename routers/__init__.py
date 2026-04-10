import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routers.auth import router as auth_router
from routers.dashboard import router as dashboard_router
from routers.transactions import router as transactions_router
from routers.categories import router as categories_router
from routers.budgets import router as budgets_router
from routers.profile import router as profile_router
from routers.admin import router as admin_router

__all__ = [
    "auth_router",
    "dashboard_router",
    "transactions_router",
    "categories_router",
    "budgets_router",
    "profile_router",
    "admin_router",
]