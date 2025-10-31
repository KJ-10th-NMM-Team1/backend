from typing import Annotated, AsyncGenerator
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import Depends
from settings.db import get_db

DbDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]
