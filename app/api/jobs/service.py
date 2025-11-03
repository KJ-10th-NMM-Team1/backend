from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
import logging
from typing import Any, Optional

import boto3
from bson import ObjectId
from bson.errors import InvalidId
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from app.config.s3 import session as aws_session  # reuse configured AWS session

from .models import JobCreate, JobRead, JobUpdateStatus
from ..project.models import ProjectPublic
from app.api.deps import DbDep

JOB_COLLECTION = "jobs"

AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
APP_ENV = os.getenv("APP_ENV", "dev").lower()
JOB_QUEUE_URL = os.getenv("JOB_QUEUE_URL")
JOB_QUEUE_FIFO = os.getenv("JOB_QUEUE_FIFO", "false").lower() == "true"
JOB_QUEUE_MESSAGE_GROUP_ID = os.getenv("JOB_QUEUE_MESSAGE_GROUP_ID")

_session = aws_session or boto3.Session(region_name=AWS_REGION)
_sqs_client = _session.client("sqs", region_name=AWS_REGION)
logger = logging.getLogger(__name__)


class SqsPublishError(Exception):
    """Raised when the job message cannot be enqueued to SQS."""


def _serialize_job(doc: dict[str, Any]) -> JobRead:
    return JobRead.model_validate(
        {
            "id": str(doc["_id"]),
            "project_id": doc["project_id"],
            "input_key": doc["input_key"],
            "status": doc["status"],
            "callback_url": doc["callback_url"],
            "result_key": doc.get("result_key"),
            "error": doc.get("error"),
            "metadata": doc.get("metadata"),
            "created_at": doc["created_at"],
            "updated_at": doc["updated_at"],
            "history": doc.get("history", []),
        }
    )


def _normalize_segment_record(segment: dict[str, Any], *, index: int) -> dict[str, Any]:
    """
    Ensure segment documents stored in MongoDB follow the schema expected by /api/segment.
    """

    def _float_or_none(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    issues = segment.get("issues") or []
    if not isinstance(issues, list):
        issues = [issues]

    assets = segment.get("assets")
    if not isinstance(assets, dict):
        assets = None

    normalized = {
        "segment_id": str(segment.get("segment_id", index)),
        "segment_text": segment.get("segment_text", ""),
        "score": segment.get("score"),
        "editor_id": segment.get("editor_id"),
        "translate_context": segment.get("translate_context", ""),
        "sub_langth": _float_or_none(segment.get("sub_langth")),
        "start_point": _float_or_none(segment.get("start_point")) or 0.0,
        "end_point": _float_or_none(segment.get("end_point")) or 0.0,
        "issues": issues,
    }

    if assets:
        normalized["assets"] = assets

    for key in ("source_key", "bgm_key", "tts_key", "mix_key", "video_key"):
        value = segment.get(key)
        if not value and assets:
            value = assets.get(key)
        if value:
            normalized[key] = str(value)

    return normalized


async def create_job(
    db: AsyncIOMotorDatabase,
    payload: JobCreate,
    *,
    job_oid: Optional[ObjectId] = None,
) -> JobRead:
    now = datetime.utcnow()
    job_oid = job_oid or ObjectId()
    document = {
        "_id": job_oid,
        "project_id": payload.project_id,
        "input_key": payload.input_key,
        "callback_url": str(payload.callback_url),
        "status": "queued",
        "result_key": None,
        "error": None,
        "metadata": payload.metadata or None,
        "created_at": now,
        "updated_at": now,
        "history": [
            {
                "status": "queued",
                "ts": now,
                "message": "job created",
            }
        ],
    }

    try:
        await db[JOB_COLLECTION].insert_one(document)
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job",
        ) from exc

    return _serialize_job(document)


async def get_job(db: AsyncIOMotorDatabase, job_id: str) -> JobRead:
    try:
        job_oid = ObjectId(job_id)
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id"
        ) from exc

    document = await db[JOB_COLLECTION].find_one({"_id": job_oid})
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    return _serialize_job(document)


async def update_job_status(
    db: AsyncIOMotorDatabase,
    job_id: str,
    payload: JobUpdateStatus,
    *,
    message: Optional[str] = None,
) -> JobRead:
    try:
        job_oid = ObjectId(job_id)
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id"
        ) from exc

    now = datetime.utcnow()
    update_operations: dict[str, Any] = {
        "$set": {
            "status": payload.status,
            "updated_at": now,
        },
        "$push": {
            "history": {
                "status": payload.status,
                "ts": now,
                "message": message or payload.message,
            }
        },
    }

    if payload.result_key is not None:
        update_operations["$set"]["result_key"] = payload.result_key

    if payload.error is not None:
        update_operations["$set"]["error"] = payload.error

    if payload.metadata is not None:
        update_operations["$set"]["metadata"] = payload.metadata

    updated = await db[JOB_COLLECTION].find_one_and_update(
        {"_id": job_oid},
        update_operations,
        return_document=ReturnDocument.AFTER,
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    project_updates: dict[str, Any] = {}
    metadata = payload.metadata if isinstance(payload.metadata, dict) else None
    if metadata:
        segments_meta = metadata.get("segments")
        if isinstance(segments_meta, list):
            normalized_segments = [
                _normalize_segment_record(
                    seg if isinstance(seg, dict) else {}, index=i
                )
                for i, seg in enumerate(segments_meta)
            ]
            project_updates["segments"] = normalized_segments
            project_updates["segments_updated_at"] = now

        assets_prefix = metadata.get("segment_assets_prefix")
        if assets_prefix:
            project_updates["segment_assets_prefix"] = assets_prefix

        target_lang = metadata.get("target_lang")
        if target_lang:
            project_updates["target_lang"] = target_lang

        source_lang = metadata.get("source_lang")
        if source_lang:
            project_updates["source_lang"] = source_lang

        metadata_key = metadata.get("metadata_key")
        if metadata_key:
            project_updates["segment_metadata_key"] = metadata_key

        result_key_meta = metadata.get("result_key")
        if result_key_meta:
            project_updates["segment_result_key"] = result_key_meta

    if payload.status:
        project_updates.setdefault("status", payload.status)

    project_id = updated.get("project_id")
    if project_updates and project_id:
        try:
            project_oid = ObjectId(project_id)
        except InvalidId:
            project_oid = None
        if project_oid:
            try:
                await db["projects"].update_one(
                    {"_id": project_oid},
                    {"$set": project_updates},
                )
            except PyMongoError as exc:
                logger.error(
                    "Failed to update project %s with segment metadata: %s",
                    project_id,
                    exc,
                )

    return _serialize_job(updated)


async def mark_job_failed(
    db: AsyncIOMotorDatabase,
    job_id: str,
    *,
    error: str,
    message: Optional[str] = None,
) -> JobRead:
    payload = JobUpdateStatus(
        status="failed", error=error, result_key=None, message=message
    )
    return await update_job_status(db, job_id, payload, message=message)


async def enqueue_job(job: JobRead) -> None:
    if not JOB_QUEUE_URL:
        if APP_ENV in {"dev", "development", "local"}:
            logger.warning(
                "JOB_QUEUE_URL not set; skipping SQS enqueue for job %s in %s environment",
                job.job_id,
                APP_ENV,
            )
            return
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JOB_QUEUE_URL env not set",
        )

    message_body = json.dumps(
        {
            "job_id": job.job_id,
            "project_id": job.project_id,
            "input_key": job.input_key,
            "callback_url": str(job.callback_url),
        }
    )

    message_kwargs: dict[str, Any] = {
        "QueueUrl": JOB_QUEUE_URL,
        "MessageBody": message_body,
        "MessageAttributes": {
            "job_id": {"StringValue": job.job_id, "DataType": "String"},
            "project_id": {"StringValue": job.project_id, "DataType": "String"},
        },
    }

    if JOB_QUEUE_FIFO:
        group_id = JOB_QUEUE_MESSAGE_GROUP_ID or job.project_id
        message_kwargs["MessageGroupId"] = group_id
        message_kwargs["MessageDeduplicationId"] = job.job_id

    try:
        await asyncio.to_thread(_sqs_client.send_message, **message_kwargs)
    except (BotoCoreError, ClientError) as exc:
        if APP_ENV in {"dev", "development", "local"}:
            logger.error("SQS publish failed in %s env: %s", APP_ENV, exc)
            return
        raise SqsPublishError("Failed to publish job message to SQS") from exc


async def start_job(project: ProjectPublic, db: DbDep):
    callback_base = os.getenv("JOB_CALLBACK_BASE_URL")
    if not callback_base:
        app_env = os.getenv("APP_ENV", "dev").lower()
        if app_env in {"dev", "development", "local"}:
            callback_base = "http://localhost:8000"
        else:
            raise HTTPException(
                status_code=500, detail="JOB_CALLBACK_BASE_URL env not set"
            )

    job_oid = ObjectId()
    callback_url = f"{callback_base.rstrip('/')}/api/jobs/{job_oid}/status"
    job_payload = JobCreate(
        project_id=project.project_id,
        input_key=project.video_source,
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

    return {
        "project_id": project.project_id,
        "job_id": job.job_id,
        "status": job.status,
    }
