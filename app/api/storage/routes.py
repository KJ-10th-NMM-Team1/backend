# app/api/routes/upload.py
import os
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from app.api.jobs.models import JobCreate
from app.api.jobs.service import SqsPublishError, create_job, enqueue_job, mark_job_failed
from app.api.projects.service import create_project, update_project
from app.config.s3 import s3
from ..deps import DbDep
from ..projects.models import ProjectUpdate
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

    callback_base = os.getenv("JOB_CALLBACK_BASE_URL")
    if not callback_base:
        app_env = os.getenv("APP_ENV", "dev").lower()
        if app_env in {"dev", "development", "local"}:
            callback_base = "http://localhost:8000"
        else:
            raise HTTPException(status_code=500, detail="JOB_CALLBACK_BASE_URL env not set")

    job_oid = ObjectId()
    callback_url = f"{callback_base.rstrip('/')}/api/jobs/{job_oid}/status"
    job_payload = JobCreate(
        project_id=result["project_id"],
        input_key=payload.object_key,
        callback_url=callback_url,
    )
    job = await create_job(db, job_payload, job_oid=job_oid)

    try:
        await enqueue_job(job)
    except SqsPublishError as exc:
        await mark_job_failed(
            db,
            job.job_id,
            error="sqs_publish_failed",
            message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue job",
        ) from exc

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "project_id": result["project_id"],
            "job_id": job.job_id,
            "status": job.status,
        },
    )


# @upload_router.post("/fail-upload")
# async def fail_upload(payload: PresignRequest, db: DbDep):
#     pass
