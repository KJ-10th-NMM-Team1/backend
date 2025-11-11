from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from ..deps import DbDep
from .models import AssetCreate, AssetOut


class AssetService:
    def __init__(self, db: DbDep):
        self.db = db
        self.asset_collection = db.get_collection("assets")

    async def create_asset(self, payload: AssetCreate) -> AssetOut:
        doc = payload.model_dump()
        doc["created_at"] = datetime.now()
        result = await self.asset_collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return AssetOut.model_validate(doc)

    async def list_assets(
        self,
        project_id: str,
        language_code: Optional[str] = None,
        type: Optional[str] = None,
    ) -> List[AssetOut]:
        query = {"project_id": project_id}
        if language_code:
            query["language_code"] = language_code
        if type:
            query["type"] = type

        cursor = self.asset_collection.find(query).sort("created_at", -1)
        docs = await cursor.to_list(length=None)
        return [AssetOut.model_validate(doc) for doc in docs]

    async def get_asset(self, asset_id: str) -> AssetOut:
        asset_oid = self._as_object_id(asset_id)
        doc = await self.asset_collection.find_one({"_id": asset_oid})
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset not found",
            )
        return AssetOut.model_validate(doc)

    def _as_object_id(self, value: str) -> ObjectId:
        try:
            return ObjectId(value)
        except InvalidId as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid asset_id",
            ) from exc
