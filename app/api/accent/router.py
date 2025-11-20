from fastapi import APIRouter, Depends, status, Query
from typing import List, Optional
from .models import Accent, AccentCreate
from .service import AccentService
from ..deps import DbDep

router = APIRouter(prefix="/accents", tags=["accents"])

def service(db: DbDep) -> AccentService:
    return AccentService(db)

DEFAULT_ACCENTS = [
    # Korean
    AccentCreate(language_code="ko", name="표준어", code="standard"),
    AccentCreate(language_code="ko", name="충청도", code="chungcheong"),
    AccentCreate(language_code="ko", name="경상도", code="gyeongsang"),
    AccentCreate(language_code="ko", name="전라도", code="jeolla"),
    # English
    AccentCreate(language_code="en", name="American", code="american"),
    AccentCreate(language_code="en", name="British", code="british"),
    AccentCreate(language_code="en", name="Australian", code="australian"),
    AccentCreate(language_code="en", name="Indian", code="indian"),
    # Japanese
    AccentCreate(language_code="jp", name="Standard (Tokyo)", code="standard"),
    AccentCreate(language_code="jp", name="Kansai (Osaka/Kyoto)", code="kansai"),
]

@router.get("", response_model=List[Accent])
async def list_accents(
    language_code: Optional[str] = Query(None, description="Filter by language code"),
    svc: AccentService = Depends(service)
):
    return await svc.list_accents(language_code)

@router.post("/defaults", response_model=List[Accent])
async def ensure_default_accents(svc: AccentService = Depends(service)):
    return await svc.ensure_defaults(DEFAULT_ACCENTS)
