# app/api/routes/upload.py
import os
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.config.s3 import s3
from .models import PresignRequest, UploadFinalize
from ..project.models import ProjectUpdate
from ..deps import DbDep
from app.api.project.service import create_project, update_project

upload_router = APIRouter(prefix="/storage", tags=["storage"])


@upload_router.post("/prepare-upload")
async def prepare_upload(payload: PresignRequest, db: DbDep):
    bucket = os.getenv("AWS_S3_BUCKET")
    if not bucket:
        raise HTTPException(status_code=500, detail="AWS_S3_BUCKET env not set")

    project = await create_project(db, payload)
    project_id = project["project_id"]

    object_key = f"projects/{project_id}/inputs/videos/{uuid4()}_{payload.filename}"

    try:
        presigned = s3.generate_presigned_post(
            Bucket=bucket,
            Key=object_key,
            Fields={"Content-Type": payload.content_type},
            Conditions=[
                ["starts-with", "$Content-Type", payload.content_type.split("/")[0]]
            ],
            ExpiresIn=300,  # 5분
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"presign 실패: {exc}")

    return {
        "project_id": project_id,
        "upload_url": presigned["url"],
        "fields": presigned["fields"],
        "object_key": object_key,
    }


@upload_router.post("/finish-upload")
async def fin_upload(payload: UploadFinalize, db: DbDep):
    update_payload = ProjectUpdate(
        project_id=payload.project_id,
        status="upload_done",
        video_source=payload.object_key,
    )
    return await update_project(db, update_payload)
    # return update_payload


# @upload_router.post("/fail-upload")
# async def fail_upload(payload: PresignRequest, db: DbDep):
#     pass
