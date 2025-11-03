from ..deps import DbDep
from .model import ResponseSegment
from typing import List


class SegmentService:
    def __init__(self, db: DbDep):
        self.collection_name = "projects"
        self.collection = db.get_collection(self.collection_name)
        self.projection = {
            "segments": 1,
            "editor_id": 1,
        }

    async def find_all_segment(self):
        project_docs = await self.collection.find({}, self.projection).to_list(
            length=None
        )

        all_segments: List[ResponseSegment] = []

        for project_doc in project_docs:
            project_id = project_doc["_id"]
            editor_id = project_doc.get("editor_id")
            segments = project_doc.get("segments") or []
            for segment_data in segments:
                segment_data = dict(segment_data)
                segment_data["_id"] = project_id
                segment_data.setdefault("editor_id", editor_id)
                all_segments.append(ResponseSegment(**segment_data))

        return all_segments
