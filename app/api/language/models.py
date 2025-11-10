from typing import Optional
from pydantic import BaseModel, Field

class LanguageBase(BaseModel):
    name_ko: str = Field(..., min_length=1)
    name_en: str = Field(..., min_length=1)

class LanguageCreate(LanguageBase):
    language_code: str = Field(..., min_length=2, max_length=8)

class LanguageUpdate(LanguageBase):
    pass  # name 변경만 허용

class Language(LanguageCreate):
    class Config:
        orm_mode = True