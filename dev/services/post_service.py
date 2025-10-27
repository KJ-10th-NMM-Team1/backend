from fastapi import Depends
from dev.config.database import get_db
from typing import List, Dict, Any
from dev.model.models import PostCreate, PostOut
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timedelta, timezone

class PostService:
    def __init__(self, db: AsyncIOMotorDatabase = Depends(get_db)):
        self.collection_name = 'posts'
        self.collection = db.get_collection(self.collection_name)

    async def post_find_one(self, id: str)->PostOut:
        result = await self.collection.find_one({'_id': ObjectId(id)})
        
        return PostOut(**result)
    
    async def post_count(self)->int:
        return await self.collection.count_documents({})

    async def post_find_all(
        self,
        sort: str = 'createdAt',
        page: int = 1,     
        limit: int = 10,   
    ) -> List[PostOut]:
        
        skip = (page - 1) * limit

        cursor = self.collection.find({}) \
                               .sort({sort: -1}) \
                               .skip(skip) \
                               .limit(limit)
        
        documents_as_dict = await cursor.to_list(length=limit)
        return [PostOut(**doc) for doc in documents_as_dict]
        
    async def post_insert(self, post_data: PostCreate, auth_id: str, auth_name: str)->str:
        result = await self.collection.insert_one({'auth_id': auth_id, 'auth_name': auth_name,
                                                    'title': post_data.title, 'content': post_data.content, 
                                                    'viewCount': 0, 'createdAt': datetime.now(timezone.utc), 'updatedAt': datetime.now(timezone.utc)})
        return str(result.inserted_id)

    async def post_delete_one(self, id: str)->bool:
        result = await self.collection.delete_one({'_id': ObjectId(id)})
        return result.deleted_count > 0

    async def post_delete_all(self)->int:
        result = await self.collection.delete_many({})
        return result.deleted_count
    
    async def post_update(self, id: str, new_post: PostCreate)->PostOut:
        self.collection.update_one({'_id': ObjectId(id)}, {'$set': {'title': new_post.title, 'content': new_post.content, 
                                                    'updatedAt': datetime.now(timezone.utc)}})
        return id
        

