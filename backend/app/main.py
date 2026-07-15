from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.knowledge import router as knowledge_router
from app.api.diagnosis import router as diagnosis_router
from app.api.teacher import router as teacher_router
from app.api.recommendations import router as recommendations_router
from app.api.students import router as students_router
from app.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(admin_router, prefix=settings.api_prefix)
app.include_router(knowledge_router, prefix=settings.api_prefix)
app.include_router(diagnosis_router, prefix=settings.api_prefix)
app.include_router(teacher_router, prefix=settings.api_prefix)
app.include_router(recommendations_router, prefix=settings.api_prefix)
app.include_router(students_router, prefix=settings.api_prefix)

frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    assets = frontend_dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa_fallback(path: str) -> FileResponse:
        return FileResponse(frontend_dist / "index.html")
