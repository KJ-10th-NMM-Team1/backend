from fastapi import APIRouter

from .storage.routes import upload_router
from app.router.editor_router import editor_router

api_router = APIRouter(prefix="/api")
api_router.include_router(upload_router)
api_router.include_router(editor_router, prefix="/editor", tags=["editor"])
