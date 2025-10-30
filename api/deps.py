from typing import Annotated, AsyncGenerator
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import Depends
from settings.db import make_db

# async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase]:
#     yield db

DbDep = Annotated[AsyncIOMotorDatabase, Depends(make_db)]
