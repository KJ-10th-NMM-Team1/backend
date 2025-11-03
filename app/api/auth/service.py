import os
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from ...config.env import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from ..deps import DbDep
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from .model import User, UserCreate, UserOut


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class AuthService:
    def __init__(self, db: DbDep):
        self.collection_name = "users"
        self.collection = db.get_collection(self.collection_name)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """입력된 비밀번호와 해시된 비밀번호를 비교합니다."""
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """비밀번호를 해싱합니다."""
        return pwd_context.hash(password)

    async def get_user_by_email(self, email: str):
        return await self.collection.find_one({"email": email})

    def create_access_token(
        self, data: dict, expires_delta: Optional[timedelta] = None
    ) -> str:
        """JWT Access Token을 생성합니다."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=ACCESS_TOKEN_EXPIRE_MINUTES
            )

        to_encode.update({"exp": expire})

        # "sub" (subject)는 토큰의 주체(사용자)를 나타내는 표준 필드입니다.
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    async def create_user(self, user_data: UserCreate) -> UserOut:

        # 1. 🔑 중복 사용자 확인 (Username)
        existing_user = await self.collection.find_one({"username": user_data.username})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 사용 중인 사용자 이름입니다.",
            )

        # 2. 🔑 중복 이메일 확인
        existing_email = await self.collection.find_one({"email": user_data.email})
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 등록된 이메일입니다.",
            )

        # 3. 비밀번호 해싱
        hashed_password = self.get_password_hash(user_data.hashed_password)

        # 4. DB에 저장할 문서(dict) 생성
        user_doc = user_data.model_dump()  # Pydantic 모델을 dict로 변환
        user_doc["hashed_password"] = hashed_password  # 👈 해시된 비밀번호 저장
        user_doc["createdAt"] = datetime.now(timezone.utc)  # 👈 가입 시간 추가

        # 5. DB에 삽입
        result = await self.collection.insert_one(user_doc)

        # 6. 방금 생성된 사용자 정보를 다시 조회하여 반환
        new_user = await self.collection.find_one({"_id": result.inserted_id})
        return UserOut(**new_user)


async def get_current_user(db: DbDep, token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # 1. 토큰 검증
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # 2. 'sub' (사용자 ID 또는 이메일) 추출
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # 3. DB에서 실제 사용자 조회
    user = await db.get_collection("users").find_one({"email": email})
    if user is None:
        raise credentials_exception

    # 4. (선택적) Pydantic 모델로 변환하여 반환
    return User(**user)
