from datetime import datetime
from typing import Optional, Sequence

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from ..auth.model import UserOut
from ..voice_samples.service import VoiceSampleService
from ..voice_samples.models import VoiceSampleOut
from .models import CreditPackage


DEFAULT_PACKAGES: Sequence[CreditPackage] = [
    CreditPackage(id="pack-starter", label="스타터 1,000", credits=1000, priceKRW=9900, bonusCredits=0),
    CreditPackage(id="pack-pro", label="프로 5,000", credits=5000, priceKRW=44900, bonusCredits=250),
    CreditPackage(id="pack-team", label="팀 10,000", credits=10000, priceKRW=84900, bonusCredits=1000),
    CreditPackage(id="pack-elite", label="엘리트 20,000", credits=20000, priceKRW=159900, bonusCredits=2500),
]


class CreditService:
    def __init__(self, db: AsyncIOMotorDatabase, packages: Optional[Sequence[CreditPackage]] = None):
        self.db = db
        self.packages = list(packages) if packages is not None else list(DEFAULT_PACKAGES)
        self.balance_collection = db["credit_balances"]
        self.tx_collection = db["credit_transactions"]
        self.voice_service = VoiceSampleService(db)

    async def get_balance(self, user: UserOut) -> int:
        """유저 크레딧 잔액을 조회/초기화"""
        try:
            user_oid = ObjectId(user.id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")

        doc = await self.balance_collection.find_one({"user_id": user_oid})
        if not doc:
            await self.balance_collection.update_one(
                {"user_id": user_oid},
                {"$setOnInsert": {"balance": 0, "created_at": datetime.utcnow()}},
                upsert=True,
            )
            return 0
        return int(doc.get("balance", 0))

    async def list_packages(self) -> list[CreditPackage]:
        return self.packages

    async def purchase_package(self, user: UserOut, package_id: str) -> int:
        pkg = next((p for p in self.packages if p.id == package_id), None)
        if not pkg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid packageId")

        try:
            user_oid = ObjectId(user.id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")

        increment = pkg.credits + (pkg.bonusCredits or 0)
        result = await self.balance_collection.find_one_and_update(
            {"user_id": user_oid},
            {
                "$inc": {"balance": increment},
                "$setOnInsert": {"created_at": datetime.utcnow()},
                "$set": {"updated_at": datetime.utcnow()},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        new_balance = int(result.get("balance", 0)) if result else increment

        await self.tx_collection.insert_one(
            {
                "user_id": user_oid,
                "type": "purchase_package",
                "package_id": pkg.id,
                "credits": increment,
                "balance": new_balance,
                "created_at": datetime.utcnow(),
            }
        )
        return new_balance

    async def purchase_voice(self, user: UserOut, sample_id: str, cost: int) -> int:
        """크레딧 차감 + 보이스 추가를 하나의 흐름으로 처리 (단일 쓰기 시도)"""
        if cost < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cost")

        # 샘플 검증
        sample = await self._fetch_voice(sample_id, user)
        if not sample.is_public:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="비공개 보이스는 추가할 수 없습니다.")
        if sample.can_commercial_use is False:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="비상업용 보이스는 추가할 수 없습니다.")
        if sample.owner_id and str(sample.owner_id) == user.id:
            # 소유자 본인은 차감 없이 바로 추가
            await self.voice_service.add_to_my_voices(sample_id, user)
            return await self.get_balance(user)

        try:
            user_oid = ObjectId(user.id)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user id")

        # 크레딧 차감 (잔액 조건 포함)
        updated = await self.balance_collection.find_one_and_update(
            {"user_id": user_oid, "balance": {"$gte": cost}},
            {"$inc": {"balance": -cost}, "$set": {"updated_at": datetime.utcnow()}},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="크레딧이 부족합니다.")

        # 보이스 추가 (이미 있으면 롤백 없이 통과하되 잔액 유지)
        await self.voice_service.add_to_my_voices(sample_id, user)

        new_balance = int(updated.get("balance", 0))
        await self.tx_collection.insert_one(
            {
                "user_id": user_oid,
                "type": "purchase_voice",
                "sample_id": sample_id,
                "cost": cost,
                "balance": new_balance,
                "created_at": datetime.utcnow(),
            }
        )
        return new_balance

    async def _fetch_voice(self, sample_id: str, user: UserOut) -> VoiceSampleOut:
        sample = await self.voice_service.get_voice_sample(sample_id, current_user=user)
        if not sample:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice sample not found")
        return sample
