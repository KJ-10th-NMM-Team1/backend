from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi import Request
from datetime import timedelta
from .model import UserCreate, UserOut, UserLogin, GoogleLogin
from typing import Dict, Any
from .service import AuthService, get_current_user_from_cookie
from ...config.env import ACCESS_TOKEN_EXPIRE_MINUTES
from ...config.env import REFRESH_TOKEN_EXPIRE_DAYS
from .model import RefreshTokenRequest

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

    # 6. Access Token 생성
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": user["email"]},  # 👈 'sub'에 사용자 식별자 저장
        expires_delta=access_token_expires,
    )

    # Refresh Token 생성 및 DB에 저장
    refresh_token = auth_service.create_refresh_token(data={"sub": user["email"]})
    await auth_service.update_user_session_token(user["email"], refresh_token)

    response.set_cookie(
        key="access_token",  # 👈 쿠키의 이름
        value=f"Bearer {access_token}",  # 👈 쿠키의 값 (Bearer 접두사 포함)
        httponly=True,  # 👈 [중요] JavaScript에서 접근 불가
        # secure=True,  # 👈 (운영 환경) HTTPS에서만 전송
        # samesite="strict",  # 👈 (운영 환경) CSRF 방어
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 👈 쿠키 만료 시간 (초 단위)
    )

    response.set_cookie(
        key="refresh_token",
        value=f"Bearer {refresh_token}",
        httponly=True,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )

    # 7. 토큰 반환
    return {"message": "Login successful"}


@auth_router.post("/refresh", response_model=Dict[str, Any])
async def refresh_access_token(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(AuthService),
):
    # 쿠키에서 refresh_token 읽기
    refresh_token_cookie = request.cookies.get("refresh_token")
    if not refresh_token_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found in cookie",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # "Bearer <token>" 형식에서 토큰 추출
    try:
        scheme, refresh_token_value = refresh_token_cookie.split()
        if scheme.lower() != "bearer":
            raise ValueError
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Refresh Token 검증
    token_data = await auth_service.verify_refresh_token(refresh_token_value)

    # 새 Access Token 생성
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = auth_service.create_access_token(
        data={"sub": token_data["sub"]},
        expires_delta=access_token_expires,
    )

    # 새 Access Token 쿠키에 저장
    response.set_cookie(
        key="access_token",
        value=f"Bearer {new_access_token}",
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {"message": "Token refreshed successfully"}


@auth_router.post("/logout", response_model=Dict[str, str])
async def logout(
    response: Response,
    current_user: UserOut = Depends(get_current_user_from_cookie),
    auth_service: AuthService = Depends(AuthService),
):
    # DB에서 refresh token 제거
    await auth_service.update_user_session_token(current_user.email, "")

    response.set_cookie(
        key="access_token",
        value="",  # 👈 값을 비움
        httponly=True,
        # secure=True,
        # samesite="strict",
        samesite="lax",
        max_age=0,  # 👈 즉시 만료
    )

    response.set_cookie(
        key="refresh_token",
        value="",
        httponly=True,
        samesite="lax",
        max_age=0,
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

    # google_sub를 sub로 사용
    user_identifier = user["google_sub"]

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_service.create_access_token(
        data={"sub": user_identifier},
        expires_delta=access_token_expires,
    )

    # Refresh Token 생성 및 저장
    refresh_token = auth_service.create_refresh_token(data={"sub": user_identifier})
    await auth_service.update_user_session_token(user_identifier, refresh_token)

    response.set_cookie(
        key="access_token",
        value=f"Bearer{access_token}",
        httponly=True,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    response.set_cookie(
        key="refresh_token",
        value=f"Bearer {refresh_token}",
        httponly=True,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )

    return {"message": "Login successful", "user": UserOut(**user)}
