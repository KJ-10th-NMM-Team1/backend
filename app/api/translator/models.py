from datetime import datetime
from enum import Enum
from typing import Annotated

from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, EmailStr, Field


PyObjectId = Annotated[
    str, BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)
]


class TranslatorStatus(str, Enum):
    active = "active"
    inactive = "inactive"


class TranslatorBase(BaseModel):
    name: str
    email: EmailStr
    languages: list[str] = Field(..., min_length=1)
    status: TranslatorStatus = TranslatorStatus.active


class TranslatorCreate(TranslatorBase):
    pass


class TranslatorUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    languages: list[str] | None = Field(None, min_length=1)
    status: TranslatorStatus | None = None


class TranslatorOut(TranslatorBase):
    id: PyObjectId = Field(validation_alias="_id")
    created_at: datetime =  Field(serialization_alias="createdAt")
    updated_at: datetime =  Field(serialization_alias="updatedAt")
