
from bson import ObjectId
from fastapi import APIRouter, HTTPException, status
 # FastAPI 응답 타입 힌트를 위해 제네릭 타입 불러옴
from typing import Any, Dict, List

from app.api.deps import DbDep

router = APIRouter(prefix="/projects", tags=["Projects"])

 # MongoDB의 ObjectId·중첩 리스트/딕셔너리를 JSON 직렬화 가능한 값으로 변환
def _serialize(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value

@router.get("/", summary="프로젝트 목록 조회")
async def list_projects(db: DbDep) -> List[Dict[str, Any]]:
    projects = await db["projects"].find().to_list(length=None)
    if projects is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="프로젝트 정보를 불러오지 못했습니다.",
        )
    return [_serialize(doc) for doc in projects]