from fastapi import APIRouter

from .storage.routes import upload_router
from .preview.router import preview_router
from .project.router import project_router
from .segment.router import segment_router

api_router = APIRouter(prefix="/api")
api_router.include_router(upload_router)
api_router.include_router(preview_router)
api_router.include_router(project_router)
api_router.include_router(segment_router)
