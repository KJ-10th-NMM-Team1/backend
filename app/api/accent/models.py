from pydantic import BaseModel, Field, BeforeValidator
from typing import Optional, Annotated
from bson import ObjectId

PyObjectId = Annotated[
    str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)
]

class Accent(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    language_code: str = Field(..., description="Language code (e.g., ko, en)")
    name: str = Field(..., description="Display name of the accent")
    code: str = Field(..., description="Internal code for the accent")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

class AccentCreate(BaseModel):
    language_code: str
    name: str
    code: str


class AccentUpdate(BaseModel):
    language_code: Optional[str] = None
    name: Optional[str] = None
    code: Optional[str] = None
