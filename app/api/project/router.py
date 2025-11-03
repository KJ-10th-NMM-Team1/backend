from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, status
from typing import Any, Dict, List
from app.api.deps import DbDep

project_router = APIRouter(prefix="/projects", tags=["Projects"])


# MongoDB의 ObjectId·중첩 리스트/딕셔너리를 JSON 직렬화 가능한 값으로 변환
def _serialize(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


@project_router.get("/", summary="프로젝트 목록 조회")
async def list_projects(db: DbDep) -> List[Dict[str, Any]]:
    projects = await db["projects"].find().to_list(length=None)
    if projects is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="프로젝트 정보를 불러오지 못했습니다.",
        )
    return [_serialize(doc) for doc in projects]


@project_router.get("/{project_id}", summary="프로젝트 상세 조회")
async def get_project(project_id: str, db: DbDep) -> Dict[str, Any]:
    try:
        project_oid = ObjectId(project_id)
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project_id"
        ) from exc

    doc = await db["projects"].find_one({"_id": project_oid})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    return _serialize(doc)
