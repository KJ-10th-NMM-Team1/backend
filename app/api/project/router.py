from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List

from app.api.deps import DbDep
from .models import ProjectOut

from app.api.auth.model import UserOut
from app.api.auth.service import get_current_user_from_cookie

project_router = APIRouter(prefix="/projects", tags=["Projects"])


@project_router.get(
    "/me",
    response_model=List[ProjectOut],
    summary="현재 사용자 프로젝트 목록",
)
async def list_my_projects(
    db: DbDep,
    current_user: UserOut = Depends(get_current_user_from_cookie),
) -> List[ProjectOut]:
    docs = (
        await db["projects"]
        .find({"owner_code": current_user.id})
        .sort("created_at", -1)
        .to_list(length=None)
    )
    return [ProjectOut.model_validate(doc) for doc in docs]


@project_router.get("/", response_model=List[ProjectOut], summary="프로젝트 전체 목록")
async def list_projects(db: DbDep) -> List[ProjectOut]:
    docs = await db["projects"].find().sort("created_at", -1).to_list(length=None)

    return [ProjectOut.model_validate(doc) for doc in docs]


@project_router.get(
    "/{project_id}", response_model=ProjectOut, summary="프로젝트 상세 조회"
)
async def get_project(project_id: str, db: DbDep) -> ProjectOut:
    try:
        project_oid = ObjectId(project_id)
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project_id",
        ) from exc

    doc = await db["projects"].find_one({"_id": project_oid})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return ProjectOut.model_validate(doc)
