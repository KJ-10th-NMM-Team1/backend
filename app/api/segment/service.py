from ..deps import DbDep
from .model import ResponseSegment
from typing import List

class SegmentService:
    def __init__(self, db: DbDep):
        self.collection_name = 'projects'
        self.collection = db.get_collection(self.collection_name)
        self.projection = {
            'segments': 1,
            'editor_id': 1,
        }
    
    async def find_all_segment(self):
        project_docs = await self.collection.find({}, self.projection).to_list(length=None)

        all_segments: List[ResponseSegment] = []

        for project_doc in project_docs:
            project_id = project_doc['_id']
            editor_id = project_doc['editor_id']
            for segment_data in project_doc['segments']:
                segment_data['_id'] = project_id
                segment_data['editor_id'] = editor_id
                all_segments.append(ResponseSegment(**segment_data))

        return all_segments
