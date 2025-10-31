# app/api/routes/upload.py
import os
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.config.s3 import s3

upload_router = APIRouter(prefix="/storage", tags=["storage"])


@upload_router.post("/presigned")
async def create_presigned_upload(filename: str, content_type: str):
    bucket = os.getenv("AWS_S3_BUCKET")
    if not bucket:
        raise HTTPException(status_code=500, detail="AWS_S3_BUCKET env not set")

    object_key = f"uploads/{datetime.now():%Y/%m/%d}/{uuid4()}_{filename}"

    try:
        presigned = s3.generate_presigned_post(
            Bucket=bucket,
            Key=object_key,
            Fields={"Content-Type": content_type},
            Conditions=[["starts-with", "$Content-Type", content_type.split("/")[0]]],
            ExpiresIn=300,  # 5분
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"presign 실패: {exc}")

    return {
        "upload_url": presigned["url"],
        "fields": presigned["fields"],
        "object_key": object_key,
    }
