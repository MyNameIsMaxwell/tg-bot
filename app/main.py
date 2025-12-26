"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import get_settings
from .db import init_db
from .logging_config import setup_logging
from .rate_limit import limiter, rate_limit_exceeded_handler
from .routers import templates as templates_router
from .telegram_client import ensure_bot_updates_listener


setup_logging()
settings = get_settings()
logger = logging.getLogger(__name__)

# CORS whitelist - only allow trusted origins
ALLOWED_ORIGINS = [
    settings.webapp_base_url,
    "https://web.telegram.org",
    "https://telegram.org",
]
# Filter out empty/None values and ensure we have at least localhost for dev
ALLOWED_ORIGINS = [origin for origin in ALLOWED_ORIGINS if origin]
if not ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = ["http://localhost:8000"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("Starting up application...")
    await init_db()
    await ensure_bot_updates_listener()
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")


app = FastAPI(
    title="Telegram Summary Mini-App",
    version="0.1.0",
    lifespan=lifespan,
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["X-Telegram-Init-Data", "Content-Type", "Authorization"],
)

frontend_dir = Path("frontend").resolve()
if frontend_dir.exists():
    app.mount("/app", StaticFiles(directory=frontend_dir, html=True), name="frontend")

app.include_router(templates_router.router)


@app.get("/health", response_class=JSONResponse)
async def healthcheck() -> JSONResponse:
    """Health check endpoint for monitoring."""
    return JSONResponse({"status": "ok"})


@app.get("/", include_in_schema=False)
async def landing() -> FileResponse:
    """Serve the frontend landing page."""
    index_file = frontend_dir / "index.html"
    if not index_file.exists():
        return FileResponse(Path(__file__).parent / "placeholder.html")
    return FileResponse(index_file)



