from fastapi import APIRouter

from .storage.routes import upload_router
from .jobs.routes import router as job_router
from .preview.router import editor_preview_router, preview_router
from .project.router import project_router
from .segment.router import segment_router, editor_segment_router
from .pipeline.router import pipeline_router
from .auth.router import auth_router
from .translate.routes import trans_router
from .translator.routes import translator_router

api_router = APIRouter(prefix="/api")

api_router.include_router(upload_router)
api_router.include_router(preview_router)
api_router.include_router(editor_preview_router)
api_router.include_router(project_router)
api_router.include_router(segment_router)
api_router.include_router(editor_segment_router)
api_router.include_router(job_router)
api_router.include_router(pipeline_router)
api_router.include_router(auth_router)
api_router.include_router(trans_router)
api_router.include_router(translator_router)
