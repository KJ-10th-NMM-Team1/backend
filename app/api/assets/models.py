from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, Field


PyObjectId = Annotated[
    str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)
]


class AssetType(str, Enum):
    PREVIEW = "preview_video"
    SUBTITLE = "subtitle_srt"
    DUBBED_AUDIO = "dubbed_audio"


class AssetBase(BaseModel):
    project_id: str
    language_code: Optional[str] = None
    asset_type: AssetType
    file_path: str
    created_at: datetime


class AssetCreate(BaseModel):
    project_id: Optional[str] = None
    language_code: Optional[str] = None
    asset_type: AssetType
    file_path: str


class AssetOut(AssetBase):
    asset_id: PyObjectId = Field(validation_alias="_id")
