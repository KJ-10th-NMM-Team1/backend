# models.py
from pydantic import ConfigDict, BaseModel, Field, BeforeValidator, EmailStr
from typing import Optional, List, Any, Annotated
from bson import ObjectId
from datetime import datetime

PyObjectId = Annotated[
    str, # 👈 최종 변환될 타입은 'str'입니다.
    BeforeValidator(lambda v: str(v) if isinstance(v, ObjectId) else v)
]

# 게시글 목록 (GET /api/posts/)을 위한 응답 모델
class PostOut(BaseModel):
    # MongoDB의 `_id` 필드를 `id`라는 이름의 문자열로 변환
    id: PyObjectId = Field(alias="_id")
    auth_id: str
    auth_name: str
    title: str
    content: str
    viewCount: int
    createdAt: datetime
    updatedAt: datetime
    
    # `_id`를 `id`로 매핑할 수 있도록 허용하는 설정
    model_config = ConfigDict(populate_by_name=True)

# 게시글 상세 (GET /api/posts/{id})를 위한 응답 모델
class PostDetailOut(PostOut):
    content: str
    viewCount: int
    createdAt: datetime

# 댓글 (GET /api/posts/{postId}/comments)을 위한 응답 모델
class CommentOut(BaseModel):
    id: PyObjectId = Field(alias="_id")
    post_id: PyObjectId = Field(alias="post_id")
    auth_id: str
    parent_id: Optional[PyObjectId] = None
    auth_name: str
    content: str
    createdAt: datetime

    model_config = ConfigDict(populate_by_name=True)

class CommentCreate(BaseModel):
    post_id: PyObjectId = Field(alias="post_id")
    content: str
    # 대댓글 기능: parent_id는 ObjectId이거나 None일 수 있습니다.
    parent_id: Optional[PyObjectId] = None

    model_config = ConfigDict(populate_by_name=True)


# (참고) 게시글 생성을 위한 입력 모델 (POST /api/posts/)
# React로부터 받을 데이터의 형식을 정의합니다.
class PostCreate(BaseModel):
    title: str = Field(..., min_length=3)
    content: str = Field(..., min_length=10)
    # author_id 등은 로그인 인증(JWT)을 통해 서버에서 직접 넣는 것이 좋습니다.

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3)
    email: EmailStr # 👈 Pydantic이 이메일 형식을 자동으로 검증
    hashed_password: str = Field(..., min_length=6, description="6자 이상")


class User(BaseModel):
    email: str
    username: str
    hashed_password: str


class UserOut(BaseModel):
    id: PyObjectId = Field(alias="_id")
    username: str
    hashed_password: str
    email: EmailStr
    createdAt: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )