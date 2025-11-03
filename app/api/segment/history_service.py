from ..deps import DbDep
from .model import RequestSegment
from typing import List


class HistoryService:
    def __init__(self, db: DbDep):
        self.collection_name = "history"
        self.collection = db.get_collection(self.collection_name)

    async def insert_one_history(self, request: RequestSegment):
        segment_dict = request.model_dump(by_alias=True, mode="python")
        result = await self.collection.insert_one(segment_dict)
        return result.inserted_id
