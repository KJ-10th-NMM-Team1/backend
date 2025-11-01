from fastapi import APIRouter

from .storage.routes import upload_router
from .preview.router import preview_router
from .project.project_router import router
from .segment.router import segment_router

api_router = APIRouter(prefix="/api")
api_router.include_router(upload_router)
api_router.include_router(preview_router)
api_router.include_router(router)
api_router.include_router(segment_router)
