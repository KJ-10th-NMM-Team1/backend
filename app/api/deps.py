from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Annotated
from fastapi import Depends
from ..config.db import get_db

DbDep = Annotated[AsyncIOMotorDatabase, Depends(get_db)]
