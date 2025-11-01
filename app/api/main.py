from fastapi import APIRouter

from .storage.routes import upload_router

api_router = APIRouter(prefix="/api")

api_router.include_router(upload_router)
