from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, Field


PyObjectId = Annotated[
    str,  # <--- str에서 ObjectId로 변경하세요.
    BeforeValidator(lambda v: ObjectId(v) if not isinstance(v, ObjectId) else v),
]

class SuggestionResponse(BaseModel):
    id: PyObjectId = Field(validation_alias="id")
    segment_id: PyObjectId = Field(validation_alias="segment_id")
    original_text: Optional[str] = None
    translate_text: Optional[str] = None
    sugession_text: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True  # PyObjectId 같은 커스텀 타입 허용
        json_encoders = {ObjectId: str}  # ObjectId를 str으로 변환


class SuggestDelete(BaseModel):
    segment_id: PyObjectId

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True  # PyObjectId 같은 커스텀 타입 허용
        json_encoders = {ObjectId: str}  # ObjectId를 str으로 변환

class SuggestSave(BaseModel):
    segment_id: PyObjectId

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True  # PyObjectId 같은 커스텀 타입 허용
        json_encoders = {ObjectId: str}  # ObjectId를 str으로 변환


class SuggestionRequest(BaseModel):
    segment_id: PyObjectId
    original_text: Optional[str] = None
    translate_text: Optional[str] = None
    sugession_text: Optional[str] = None
    created_at: datetime

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True  # PyObjectId 같은 커스텀 타입 허용
        json_encoders = {ObjectId: str}  # ObjectId를 str으로 변환