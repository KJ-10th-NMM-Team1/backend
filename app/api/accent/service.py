from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException
from bson import ObjectId
from bson.errors import InvalidId
from .models import Accent, AccentCreate, AccentUpdate

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

    def _parse_object_id(self, accent_id: str) -> ObjectId:
        try:
            return ObjectId(accent_id)
        except (InvalidId, TypeError):
            raise HTTPException(status_code=400, detail="invalid accent id")

    async def get_accent(self, accent_id: str) -> Accent:
        oid = self._parse_object_id(accent_id)
        doc = await self.collection.find_one({"_id": oid})
        if not doc:
            raise HTTPException(status_code=404, detail="accent not found")
        return Accent(**doc)

    async def create_accent(self, payload: AccentCreate) -> Accent:
        exists = await self.collection.find_one(
            {"language_code": payload.language_code, "code": payload.code}
        )
        if exists:
            raise HTTPException(status_code=409, detail="accent already exists")
        result = await self.collection.insert_one(payload.model_dump())
        return await self.get_accent(str(result.inserted_id))

    async def update_accent(self, accent_id: str, payload: AccentUpdate) -> Accent:
        oid = self._parse_object_id(accent_id)
        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
        if not update_data:
            return await self.get_accent(accent_id)
        result = await self.collection.update_one({"_id": oid}, {"$set": update_data})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="accent not found")
        return await self.get_accent(accent_id)

    async def delete_accent(self, accent_id: str) -> None:
        oid = self._parse_object_id(accent_id)
        result = await self.collection.delete_one({"_id": oid})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="accent not found")

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
