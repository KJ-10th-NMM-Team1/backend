from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


PyObjectId = Annotated[
    str,
    BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v),
]


common_model_config = ConfigDict(populate_by_name=True)


class SuggestionResponse(BaseModel):
    id: PyObjectId = Field(validation_alias="id")
    segment_id: PyObjectId = Field(validation_alias="segment_id")
    original_text: Optional[str] = None
    translate_text: Optional[str] = None
    sugession_text: Optional[str] = None

    model_config = common_model_config


class SuggestDelete(BaseModel):
    segment_id: PyObjectId

    model_config = common_model_config


class SuggestSave(BaseModel):
    segment_id: PyObjectId

    model_config = common_model_config


class SuggestionRequest(BaseModel):
    segment_id: PyObjectId
    original_text: Optional[str] = None
    translate_text: Optional[str] = None
    sugession_text: Optional[str] = None
    created_at: datetime

    model_config = common_model_config
