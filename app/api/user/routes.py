from fastapi import APIRouter, Depends, Query, Response, status
from typing import List
from ..auth.service import get_current_user_from_cookie
from ..auth.model import UserOut
from .service import UserService
from .models import UserSearchOut, UserUpdate
from ..deps import DbDep

user_router = APIRouter(prefix="/users", tags=["Users"])


@user_router.get("/me", response_model=UserOut)
async def get_current_user(
    current_user: UserOut = Depends(get_current_user_from_cookie),
):
    """
    현재 로그인한 사용자 정보 조회 API
    """
    return current_user


@user_router.get("/search", response_model=List[UserSearchOut])
async def search_users(
    db: DbDep,
    query: str = Query(..., min_length=1, description="검색어 (이름 또는 이메일)"),
    limit: int = Query(20, ge=1, le=100, description="최대 반환 개수"),
    _current_user: UserOut = Depends(get_current_user_from_cookie),  # 인증 필요
) -> List[UserSearchOut]:
    """
    사용자 검색 API
    초대하기 모달의 검색창에서 사용.
    이름 또는 이메일로 일치하는 사용자를 검색합니다.
    """
    user_service = UserService(db)
    return await user_service.search_users(query, limit)


@user_router.put("/me", response_model=UserOut)
async def update_current_user(
    update_data: UserUpdate,
    db: DbDep,
    current_user: UserOut = Depends(get_current_user_from_cookie),
) -> UserOut:
    """
    현재 로그인한 사용자 정보 수정 API

    자신의 이름을 수정합니다.
    """
    user_service = UserService(db)
    return await user_service.update_user(current_user.id, update_data, current_user)


@user_router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    response: Response,
    db: DbDep,
    current_user: UserOut = Depends(get_current_user_from_cookie),
):
    """
    계정 탈퇴 API

    자신의 계정을 삭제합니다. 삭제 후 쿠키도 자동으로 제거됩니다.
    """
    user_service = UserService(db)
    await user_service.delete_user(current_user.id, current_user)

    # 쿠키 삭제 (로그아웃과 동일)
    response.set_cookie(
        key="access_token",
        value="",
        httponly=True,
        samesite="lax",
        max_age=0,  # 즉시 만료
    )

    response.set_cookie(
        key="refresh_token",
        value="",
        httponly=True,
        samesite="lax",
        max_age=0,  # 즉시 만료
    )

    return None


@user_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_by_id(
    user_id: str,
    db: DbDep,
):
    """
    사용자 삭제 API (ID로 직접 삭제)

    Swagger UI에서 테스트용으로 사용할 수 있습니다.
    인증 없이도 호출 가능합니다.
    """
    user_service = UserService(db)
    await user_service.delete_user_by_id(user_id)
    return None
