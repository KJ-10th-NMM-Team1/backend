# app/api/routes/upload.py
import os
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from app.api.jobs.service import start_job
from app.api.project.service import create_project, update_project
from app.config.s3 import s3
from ..deps import DbDep
from ..project.models import ProjectUpdate
from ..pipeline.service import update_pipeline_stage
from ..pipeline.models import PipelineUpdate, PipelineStatus
from .models import PresignRequest, UploadFinalize

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


@upload_router.post("/finish-upload", status_code=status.HTTP_202_ACCEPTED)
async def fin_upload(payload: UploadFinalize, db: DbDep):
    update_payload = ProjectUpdate(
        project_id=payload.project_id,
        status="upload_done",
        video_source=payload.object_key,
    )
    result = await update_project(db, update_payload)
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
