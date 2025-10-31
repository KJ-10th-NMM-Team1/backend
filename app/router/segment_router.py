from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import timedelta
from typing import Dict, Any

router = APIRouter(
    prefix='/segment',        
    tags=['Segment']
)


@router.get('/', response_model='')
async def read_segment():
    pass
    




