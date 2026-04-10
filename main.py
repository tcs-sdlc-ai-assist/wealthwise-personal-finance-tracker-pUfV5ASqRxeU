import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import Base, engine
from seed import seed_database

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-5.5s [%(name)s] %(message)s",
)

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up WealthWise Finance Tracker...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except Exception:
        logger.exception("Error creating database tables.")
        raise

    try:
        seed_database()
        logger.info("Database seeding completed.")
    except Exception:
        logger.exception("Error seeding database.")

    yield

    logger.info("Shutting down WealthWise Finance Tracker...")


app = FastAPI(
    title="WealthWise Finance Tracker",
    description="A comprehensive personal finance tracking application.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

from routers.auth import router as auth_router
from routers.dashboard import router as dashboard_router
from routers.transactions import router as transactions_router
from routers.categories import router as categories_router
from routers.budgets import router as budgets_router
from routers.profile import router as profile_router
from routers.admin import router as admin_router

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(transactions_router)
app.include_router(categories_router)
app.include_router(budgets_router)
app.include_router(profile_router)
app.include_router(admin_router)


@app.get("/")
def root(request: Request):
    return RedirectResponse(url="/dashboard", status_code=303)


@app.exception_handler(404)
def not_found_handler(request: Request, exc):
    from utils.dependencies import get_current_user_optional, get_template_context
    from database import SessionLocal

    user = None
    try:
        db = SessionLocal()
        try:
            token = request.cookies.get("access_token")
            if token:
                from utils.security import verify_token
                payload = verify_token(token)
                if payload:
                    user_id = payload.get("sub")
                    if user_id:
                        from models.user import User
                        user = db.query(User).filter(User.id == user_id).first()
        finally:
            db.close()
    except Exception:
        logger.debug("Could not resolve user for 404 page.")

    context = get_template_context(request=request, user=user)

    return templates.TemplateResponse(
        request,
        "404.html",
        context=context,
        status_code=404,
    )


@app.exception_handler(500)
def internal_error_handler(request: Request, exc):
    from utils.dependencies import get_template_context

    logger.exception("Internal server error: %s", exc)

    context = get_template_context(request=request, user=None)

    return templates.TemplateResponse(
        request,
        "500.html",
        context=context,
        status_code=500,
    )