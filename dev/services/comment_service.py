from fastapi import Depends
from dev.config.database import get_db
from typing import List, Dict, Any, Tuple
from dev.model.models import CommentOut, CommentCreate
from motor.motor_asyncio import AsyncIOMotorDatabase # 타입 힌트를 위해 임포트
from bson import ObjectId
from datetime import datetime, timedelta, timezone

class CommentService:
    def __init__(self, db: AsyncIOMotorDatabase = Depends(get_db)):
        self.collection_name = 'comments'
        self.db = db
        self.collection = self.db.get_collection(self.collection_name)

    async def comment_find_one(self, comment_id: str, post_id: str)->CommentOut:
        result = await self.collection.find_one({'_id': ObjectId(comment_id), 'post_id': ObjectId(post_id)})
        return CommentOut(**result)


    async def comment_count(self)->int:
        return await self.collection.count_documents({})
    
    async def comment_find_all(
        self,
        post_id: str,
        sort: str = 'createdAt',
        page: int = 1,     
        limit: int = 10,  
    ) -> List[CommentOut]:
        
        skip = (page - 1) * limit

        cursor = self.collection.find({'post_id': ObjectId(post_id)}) \
                               .sort({sort: -1}) \
                               .skip(skip) \
                               .limit(limit)
        
        documents_as_dict = await cursor.to_list(length=limit)
        return [CommentOut(**doc) for doc in documents_as_dict]

    async def comment_insert(self, comment_data: CommentCreate, auth_id: str, auth_name: str)->str:

        result = await self.collection.insert_one({'post_id': ObjectId(comment_data.post_id), 'auth_id': auth_id, 
                                                   'parent_id': comment_data.parent_id, 'auth_name': auth_name, 
                                                   'content': comment_data.content, 'createdAt': datetime.now(timezone.utc)})
        return str(result.inserted_id)

    async def comment_delete_one(self, post_id: str, comment_id: str)->bool:
        result = await self.collection.delete_one({'_id': ObjectId(comment_id), 'post_id': ObjectId(post_id)})
        return result.deleted_count > 0
    
    async def comment_update_one(self, post_id:str, comment_id: str, comment_data: CommentCreate):
        await self.collection.update_one({'_id': ObjectId(comment_id), 'post_id': ObjectId(post_id)}, {'$set': {'content': comment_data.content}})
        return comment_id


    async def comment_delete_all(self)->int:
        result = await self.collection.delete_many({})
        return result.deleted_count

