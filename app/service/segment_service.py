from .api.deps import DbDep

class CommentService:
    def __init__(self, db: DbDep):
        self.collection_name = 'projects'
        self.db = db
        self.collection = self.db.get_collection(self.collection_name)

    async def find_sgments(self):
        return await self.collection.find({}, {'segments':1})
    

        


    