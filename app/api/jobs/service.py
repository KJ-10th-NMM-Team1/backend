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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id") from exc

    document = await db[JOB_COLLECTION].find_one({"_id": job_oid})
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job_id") from exc

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return _serialize_job(updated)


async def mark_job_failed(
    db: AsyncIOMotorDatabase,
    job_id: str,
    *,
    error: str,
    message: Optional[str] = None,
) -> JobRead:
    payload = JobUpdateStatus(status="failed", error=error, result_key=None, message=message)
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
