"""FastAPI application entrypoint."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .logging_config import setup_logging
from .routers import templates as templates_router
from .telegram_client import ensure_bot_updates_listener


setup_logging()
settings = get_settings()

app = FastAPI(title="Telegram Summary Mini-App", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = Path("frontend").resolve()
if frontend_dir.exists():
    app.mount("/app", StaticFiles(directory=frontend_dir, html=True), name="frontend")

app.include_router(templates_router.router)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    await ensure_bot_updates_listener()


@app.get("/health", response_class=JSONResponse)
async def healthcheck() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/", include_in_schema=False)
async def landing() -> FileResponse:
    index_file = frontend_dir / "index.html"
    if not index_file.exists():
        return FileResponse(Path(__file__).parent / "placeholder.html")
    return FileResponse(index_file)



