from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from ..deps import DbDep
from .model import UserSearchOut, UserUpdate
from ..auth.model import UserOut


class UserService:
    def __init__(self, db: DbDep):
        self.collection = db.get_collection("users")

    async def search_users(self, query: str, limit: int = 20) -> List[UserSearchOut]:
        """
        이름 또는 이메일로 사용자 검색

        Args:
            query: 검색어 (이름 또는 이메일)
            limit: 최대 반환 개수

        Returns:
            검색된 사용자 목록
        """
        if not query or len(query.strip()) < 1:
            return []

        # 대소문자 구분 없이 검색 (정규식 사용)
        search_pattern = {"$regex": query.strip(), "$options": "i"}

        # 이름 또는 이메일로 검색
        filter_query = {
            "$or": [{"username": search_pattern}, {"email": search_pattern}]
        }

        # 비밀번호 필드 제외하고 조회
        cursor = self.collection.find(
            filter_query, {"hashed_password": 0}  # 비밀번호 필드 제외
        ).limit(limit)

        users = await cursor.to_list(length=limit)
        return [UserSearchOut(**user) for user in users]

    async def update_user(
        self, user_id: str, update_data: UserUpdate, current_user: UserOut
    ) -> UserOut:
        """
        사용자 정보 업데이트 (보인만 수정 가능)

        Args:
            user_id: 수정할 사용자 ID
            update_data: 업데이트할 데이터
            current_user: 현재 로그인한 사용자

        Returns:
            업데이트된 사용자 정보
        """
        # ObjectId 변환 및 검증
        try:
            user_oid = ObjectId(user_id)
        except InvalidId as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user_id"
            ) from exc

        # 본인만 수정 가능
        if current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own profile",
            )

        # 사용자 존재 확인
        existing_user = await self.collection.find_one({"_id": user_oid})
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # 중복 사용자명 확인 (본인 제외)
        if update_data.username != existing_user.get("username"):
            duplicate = await self.collection.find_one(
                {"username": update_data.username, "_id": {"$ne": user_oid}}
            )
            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already exists",
                )

        # 업데이트 실행
        updated_user = await self.collection.find_one_and_update(
            {"_id": user_oid},
            {"$set": {"username": update_data.username}},
            return_document=True,  # 업데이트된 문서 반환
        )

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return UserOut(**updated_user)

    async def delete_user(self, user_id: str, current_user: UserOut) -> None:
        """
        사용자 계정 삭제 (본인만 삭제 가능)

        Args:
            user_id: 삭제할 사용자 ID
            current_user: 현재 로그인한 사용자
        """
        # ObjectId 변환 및 검증
        try:
            user_oid = ObjectId(user_id)
        except InvalidId as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user_id"
            ) from exc

        # 본인만 삭제 가능
        if current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own account",
            )

        # 사용자 존재 확인
        existing_user = await self.collection.find_one({"_id": user_oid})
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # 사용자 삭제
        result = await self.collection.delete_one({"_id": user_oid})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
