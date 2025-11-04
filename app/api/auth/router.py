from fastapi import APIRouter, Depends, HTTPException, status, Response
from datetime import timedelta
from .model import UserCreate, UserOut, UserLogin, GoogleLogin
from typing import Dict, Any
from .service import AuthService, get_current_user_from_cookie
from ...config.env import ACCESS_TOKEN_EXPIRE_MINUTES

auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@auth_router.put("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(
    user_data: UserCreate, auth_service: AuthService = Depends(AuthService)
) -> UserOut:
    return await auth_service.create_user(user_data)


@auth_router.post("/login", response_model=Dict[str, Any])
async def login_for_access_token(
    response: Response,  # 👈 [3] Response 객체를 주입받습니다.
    form_data: UserLogin,  # 👈 [4] JSON (UserLogin 모델)을 받습니다.
    auth_service: AuthService = Depends(AuthService),
):

    # 4. DB에서 사용자 찾기
    user = await auth_service.get_user_by_email(email=form_data.email)

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

    response.set_cookie(
        key="access_token",  # 👈 쿠키의 이름
        value=f"Bearer {access_token}",  # 👈 쿠키의 값 (Bearer 접두사 포함)
        httponly=True,  # 👈 [중요] JavaScript에서 접근 불가
        # secure=True,  # 👈 (운영 환경) HTTPS에서만 전송
        # samesite="strict",  # 👈 (운영 환경) CSRF 방어
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 👈 쿠키 만료 시간 (초 단위)
    )

    # 7. 토큰 반환
    return {"message": "Login successful"}


@auth_router.post("/logout", response_model=Dict[str, str])
async def logout(response: Response):
    response.set_cookie(
        key="access_token",
        value="",  # 👈 값을 비움
        httponly=True,
        # secure=True,
        # samesite="strict",
        samesite="lax",
        max_age=0,  # 👈 즉시 만료
    )

    return {"message": "Logout successful"}


@auth_router.get("/me", response_model=UserOut)
async def read_users_me(
    # [2] 이 의존성이 쿠키를 검사합니다.
    current_user: UserOut = Depends(get_current_user_from_cookie),
):
    return current_user


@auth_router.post(
    "/google/login", response_model=Dict[str, Any], status_code=status.HTTP_200_OK
)
async def login_with_google(
    response: Response,
    payload: GoogleLogin,
    auth_service: AuthService = Depends(AuthService),
) -> Dict[str, Any]:
    user = await auth_service.login_with_google(payload.id_token)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": user["email"]},
        expires_delta=access_token_expires,
    )

    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {"message": "Login successful", "user": UserOut(**user)}
