from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from .model import UserCreate, User, UserOut
from typing import Dict, Any
from .service import AuthService
from ...config.env import ACCESS_TOKEN_EXPIRE_MINUTES

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@auth_router.put(
    "/register", response_model=UserOut, status_code=status.HTTP_201_CREATED
)
async def register(
    user_data: UserCreate, auth_service: AuthService = Depends(AuthService)
) -> UserOut:
    return await auth_service.create_user(user_data)


@auth_router.post("/login", response_model=Dict[str, Any])
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(AuthService),
):

    # 4. DB에서 사용자 찾기
    user = await auth_service.get_user_by_email(email=form_data.username)

    # 5. 사용자가 없거나 비밀번호가 틀리면 401 에러
    if not user or not auth_service.verify_password(
        form_data.password, user["hashed_password"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 6. 토큰 생성
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": user["email"]},  # 👈 'sub'에 사용자 식별자 저장
        expires_delta=access_token_expires,
    )

    # 7. 토큰 반환
    return {"access_token": access_token, "token_type": "Bearer"}
