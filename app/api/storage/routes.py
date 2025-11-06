# app/api/routes/upload.py
import os
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from app.api.jobs.service import start_job
from app.api.project.service import ProjectService
from app.config.s3 import s3
from ..deps import DbDep
from bson.errors import InvalidId
from ..project.models import ProjectUpdate
from ..pipeline.service import update_pipeline_stage
from ..pipeline.models import PipelineUpdate, PipelineStatus
from .models import PresignRequest, UploadFinalize


upload_router = APIRouter(prefix="/storage", tags=["storage"])


@upload_router.post("/prepare-upload")
async def prepare_upload(
    payload: PresignRequest,
    project_service: ProjectService = Depends(ProjectService),
):
    bucket = os.getenv("AWS_S3_BUCKET")
    if not bucket:
        raise HTTPException(status_code=500, detail="AWS_S3_BUCKET env not set")
    try:
        project_id = await project_service.create_project(payload)
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project",
        ) from exc
    if not project_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Insert did not return an ID",
        )

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


@upload_router.post("/finish-upload", status_code=status.HTTP_202_ACCEPTED)
async def fin_upload(
    db: DbDep,
    payload: UploadFinalize,
    project_service: ProjectService = Depends(ProjectService),
):
    update_payload = ProjectUpdate(
        project_id=payload.project_id,
        status="upload_done",
        video_source=payload.object_key,
    )
    try:
        result = await project_service.update_project(update_payload)
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

    await update_pipeline_stage(
        db,
        PipelineUpdate(
            project_id=payload.project_id,
            stage_id="upload",
            status=PipelineStatus.COMPLETED,
            progress=100,
        ),
    )

    await start_job(result, db)
    await update_pipeline_stage(
        db,
        PipelineUpdate(
            project_id=payload.project_id,
            stage_id="upload",
            status=PipelineStatus.COMPLETED,
            progress=100,
        ),
    )

    return result


# @upload_router.post("/fail-upload")
# async def fail_upload(payload: PresignRequest, db: DbDep):
#     pass
