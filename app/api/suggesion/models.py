from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class SuggestionResponse(BaseModel):
    id: str = Field(validation_alias="_id")
    segment_id: str
    original_text: Optional[str] = None
    translate_text: Optional[str] = None
    sugession_text: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class SuggestDelete(BaseModel):
    segment_id: str


class SuggestSave(BaseModel):
    segment_id: str


class SuggestionRequest(BaseModel):
    segment_id: str
    original_text: Optional[str] = None
    translate_text: Optional[str] = None
    sugession_text: Optional[str] = None
    created_at: Optional[datetime] = None
