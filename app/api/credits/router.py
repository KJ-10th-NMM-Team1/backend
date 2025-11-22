from fastapi import APIRouter, Depends, status

from ..auth.service import get_current_user_from_cookie
from ..auth.model import UserOut
from ..deps import DbDep
from .models import (
    CreditBalanceResponse,
    CreditPackage,
    PurchaseCreditsRequest,
    PurchaseCreditsResponse,
    PurchaseVoiceRequest,
    PurchaseVoiceResponse,
)
from .service import CreditService

credits_router = APIRouter(prefix="/me", tags=["Credits"])


def _service(db: DbDep) -> CreditService:
    return CreditService(db)


@credits_router.get(
    "/credits",
    response_model=CreditBalanceResponse,
    status_code=status.HTTP_200_OK,
)
async def get_credit_balance(
    db: DbDep,
    current_user: UserOut = Depends(get_current_user_from_cookie),
):
    service = _service(db)
    balance = await service.get_balance(current_user)
    return CreditBalanceResponse(balance=balance)


@credits_router.get(
    "/credits/packages",
    response_model=list[CreditPackage],
    status_code=status.HTTP_200_OK,
)
async def list_credit_packages(
    db: DbDep,
    current_user: UserOut = Depends(get_current_user_from_cookie),
):
    # current_user는 인증 검증용
    service = _service(db)
    return await service.list_packages()


@credits_router.post(
    "/credits/purchase",
    response_model=PurchaseCreditsResponse,
    status_code=status.HTTP_200_OK,
)
async def purchase_credits(
    payload: PurchaseCreditsRequest,
    db: DbDep,
    current_user: UserOut = Depends(get_current_user_from_cookie),
):
    service = _service(db)
    new_balance = await service.purchase_package(current_user, payload.packageId)
    return PurchaseCreditsResponse(
        balance=new_balance,
        currency="CREDIT",
        purchasedPackageId=payload.packageId,
    )


@credits_router.post(
    "/voices/{sample_id}/purchase",
    response_model=PurchaseVoiceResponse,
    status_code=status.HTTP_200_OK,
)
async def purchase_voice_with_credits(
    sample_id: str,
    payload: PurchaseVoiceRequest,
    db: DbDep,
    current_user: UserOut = Depends(get_current_user_from_cookie),
):
    service = _service(db)
    new_balance = await service.purchase_voice(current_user, sample_id, payload.cost)
    return PurchaseVoiceResponse(
        balance=new_balance,
        currency="CREDIT",
        sampleId=sample_id,
    )
