from pydantic import BaseModel, Field
from typing import Optional


class CreditBalanceResponse(BaseModel):
    balance: int = Field(..., description="현재 보유 크레딧")
    currency: str = Field(default="CREDIT", description="통화 단위 (고정)")


class CreditPackage(BaseModel):
    id: str
    label: str
    credits: int
    priceKRW: int
    bonusCredits: Optional[int] = Field(default=0, description="추가로 지급되는 보너스 크레딧")


class PurchaseCreditsRequest(BaseModel):
    packageId: str


class PurchaseCreditsResponse(CreditBalanceResponse):
    purchasedPackageId: str


class PurchaseVoiceRequest(BaseModel):
    cost: int = Field(..., ge=0, description="차감할 크레딧 (서버 기준)")


class PurchaseVoiceResponse(CreditBalanceResponse):
    sampleId: str
