from fastapi import HTTPException, status
from datetime import datetime
from pymongo.errors import PyMongoError
from typing import TypedDict
from bson import ObjectId
from bson.errors import InvalidId

from ..deps import DbDep
from .modles import ProjectCreate, ProjectUpdate


class ProjectCreateResult(TypedDict):
    project_id: str


async def create_project(db: DbDep, payload: ProjectCreate) -> ProjectCreateResult:
    now = datetime.now()
    doc = {
        "title": payload.filename,
        "status": "upload_ready",
        "s3_key": None,
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = await db["projects"].insert_one(doc)
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project",
        ) from exc

    if not result.inserted_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Insert did not return an ID",
        )
    return {"project_id": str(result.inserted_id)}


async def update_project(db: DbDep, payload: ProjectUpdate) -> ProjectCreateResult:
    project_id = payload.project_id
    update_data = payload.model_dump(exclude={"project_id"}, exclude_none=True)
    update_data["updated_at"] = datetime.now()

    try:
        result = await db["projects"].update_one(
            {"_id": ObjectId(project_id)},
            {"$set": update_data},
        )
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project_id",
        ) from exc
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project",
        ) from exc

    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return {"project_id": project_id}
