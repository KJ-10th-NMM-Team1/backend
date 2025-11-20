from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
from .models import Accent, AccentCreate

class AccentService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.get_collection("accents")

    async def list_accents(self, language_code: str = None) -> List[Accent]:
        query = {}
        if language_code:
            query["language_code"] = language_code
        cursor = self.collection.find(query)
        return [Accent(**doc) async for doc in cursor]

    async def ensure_defaults(self, defaults: List[AccentCreate]) -> List[Accent]:
        results = []
        for item in defaults:
            # Update if exists, insert if not. matching by language_code and code
            result = await self.collection.find_one_and_update(
                {"language_code": item.language_code, "code": item.code},
                {"$set": item.model_dump()},
                upsert=True,
                return_document=True
            )
            results.append(Accent(**result))
        return results
