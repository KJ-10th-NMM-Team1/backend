from fastapi import APIRouter, Depends, status
from typing import List
from .models import Language, LanguageCreate, LanguageUpdate
from .service import LanguageService
from ..deps import DbDep

router = APIRouter(prefix="/languages", tags=["languages"])

def service(db: DbDep) -> LanguageService:
    return LanguageService(db)

@router.get("/", response_model=List[Language])
async def list_languages(svc: LanguageService = Depends(service)):
    return await svc.list_languages()

@router.get("/{language_code}", response_model=Language)
async def get_language(language_code: str, svc: LanguageService = Depends(service)):
    return await svc.get_language(language_code)

@router.post("/", response_model=Language, status_code=status.HTTP_201_CREATED)
async def create_language(payload: LanguageCreate, svc: LanguageService = Depends(service)):
    return await svc.create_language(payload)

@router.put("/{language_code}", response_model=Language)
async def update_language(language_code: str, payload: LanguageUpdate, svc: LanguageService = Depends(service)):
    return await svc.update_language(language_code, payload)

@router.delete("/{language_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_language(language_code: str, svc: LanguageService = Depends(service)):
    await svc.delete_language(language_code)
