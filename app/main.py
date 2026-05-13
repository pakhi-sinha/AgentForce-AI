from pathlib import Path
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.api.auth import router as auth_router
from app.core.config import settings
from app.db.sqlite import migrate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    migrate()
    logger.info("AgentForce AI started on port %s", settings.port)
    yield

app = FastAPI(
    title="AgentForce AI",
    description="Offline-first chat, memory, RAG, and voice assistant platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router, prefix="/auth")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.get("/")
async def landing() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/chat")
async def chat_app() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/app")
async def app_shell() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/login")
async def login_app() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/signup")
async def signup_app() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")

app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend-root")
