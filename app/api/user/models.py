from pydantic import BaseModel, EmailStr, Field


class UserSearchOut(BaseModel):
    """검색 결과용 사용자 모델 (비밀번호 제외)"""

    username: str
    email: EmailStr
    role: str


class UserUpdate(BaseModel):
    """사용자 정보 업데이트 모델"""

    username: str = Field(..., min_length=3, description="사용자 이름 (3자 이상)")
