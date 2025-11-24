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
            "input_key": doc.get("input_key"),
            "status": doc["status"],
            "callback_url": doc["callback_url"],
            "result_key": doc.get("result_key"),
            "error": doc.get("error"),
            "metadata": doc.get("metadata"),
            "created_at": doc["created_at"],
            "updated_at": doc["updated_at"],
            "history": doc.get("history", []),
            "task": doc.get("task"),
            "task_payload": doc.get("task_payload"),
            "target_lang": doc.get("target_lang"),  # 타겟 언어 추가
            "source_lang": doc.get("source_lang"),  # 원본 언어 추가
            "is_replace_voice_samples": doc.get(
                "is_replace_voice_samples"
            ),  # 음성샘플 자동 추천 여부
        }
    )


def _build_job_message(job: JobRead) -> dict[str, Any]:
    task = job.task or "split_up"
    message: dict[str, Any] = {
        "task": task,
        "job_id": job.job_id,
        "project_id": job.project_id,
        "callback_url": str(job.callback_url),
    }
    if job.input_key:
        message["input_key"] = job.input_key

    # 원본 언어 추가
    if job.source_lang:
        message["source_lang"] = job.source_lang

    # 타겟 언어가 있으면 메시지에 포함
    if job.target_lang:
        message["target_lang"] = job.target_lang

    if job.is_replace_voice_samples:
        message["is_replace_voice_samples"] = job.is_replace_voice_samples

    payload = job.task_payload or {}
    if task == "segment_tts":
        # segment_tts 작업의 경우 task_payload를 직접 메시지에 포함
        if payload:
            message.update(payload)
    elif payload:
        message.update(payload)

    return message


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


def _resolve_callback_base() -> str:
    callback_base = os.getenv("JOB_CALLBACK_BASE_URL")
    if callback_base:
        return callback_base

    app_env = os.getenv("APP_ENV", "dev").lower()
    if app_env in {"dev", "development", "local"}:
        return "http://localhost:8000"

    raise HTTPException(status_code=500, detail="JOB_CALLBACK_BASE_URL env not set")


def _collect_segment_assets(segment: dict[str, Any]) -> dict[str, Any]:
    assets = (segment.get("assets") or {}).copy()
    collected: dict[str, Any] = {}
    for key in ("source_key", "bgm_key", "tts_key", "mix_key", "video_key"):
        value = segment.get(key) or assets.get(key)
        if value:
            collected[key] = value
    if assets:
        collected["raw"] = assets
    return collected


def _build_segment_field_updates(segment_patch: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    try:
        index = int(segment_patch.get("segment_index"))
    except (TypeError, ValueError):
        return updates

    base = f"segments.{index}"

    translate_context = segment_patch.get("translate_context")
    if translate_context is not None:
        updates[f"{base}.translate_context"] = translate_context

    for key in ("tts_key", "mix_key"):
        value = segment_patch.get(key)
        if value:
            updates[f"{base}.{key}"] = value
            updates[f"{base}.assets.{key}"] = value

    return updates


def _build_segment_tts_task_payload(
    project: dict[str, Any],
    *,
    segment_index: int,
    segment: dict[str, Any],
    text: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project_id": str(project["_id"]),
        "segment_index": segment_index,
        "segment_id": str(segment.get("segment_id", segment_index)),
        "text": text,
        "segment_text": segment.get("segment_text"),
        "start_point": float(segment.get("start_point", 0.0) or 0.0),
        "end_point": float(segment.get("end_point", 0.0) or 0.0),
        "assets": _collect_segment_assets(segment),
        "segment_assets_prefix": project.get("segment_assets_prefix"),
    }

    source_keys = []
    assets = payload["assets"]
    value = assets.get("source_key")
    if value:
        source_keys.append(value)
    raw_assets = segment.get("assets") or {}
    extra_sources = raw_assets.get("source_keys") or raw_assets.get("source_list")
    if isinstance(extra_sources, list):
        source_keys.extend(str(item) for item in extra_sources if item)
    payload["source_keys"] = list(dict.fromkeys(source_keys))

    if project.get("target_lang"):
        payload["target_lang"] = project["target_lang"]
    if project.get("source_lang"):
        payload["source_lang"] = project["source_lang"]
    if segment.get("sub_langth") is not None:
        try:
            payload["sub_length"] = float(segment["sub_langth"])
        except (TypeError, ValueError):
            pass

    return payload


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
        "task": payload.task or "split_up",
        "task_payload": payload.task_payload or None,
        "target_lang": payload.target_lang,  # 타겟 언어 저장
        "source_lang": payload.source_lang,  # 원본 언어 저장
        "is_replace_voice_samples": payload.is_replace_voice_samples,  # 음성샘플 자동 추천 여부
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

    now = datetime.now()
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

    # if payload.metadata is not None:
    #     update_operations["$set"]["metadata"] = payload.metadata.model_dump()

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
        # metadata에 stage가 있으면 project의 status를 업데이트
        stage = metadata.get("stage")
        if stage:
            project_updates["status"] = stage

        # segments_meta = metadata.get("segments")
        # if isinstance(segments_meta, list):
        #     normalized_segments = [
        #         _normalize_segment_record(seg if isinstance(seg, dict) else {}, index=i)
        #         for i, seg in enumerate(segments_meta)
        #     ]
        #     project_updates["segments"] = normalized_segments
        #     project_updates["segments_updated_at"] = now

        assets_prefix = metadata.get("segment_assets_prefix")
        if assets_prefix:
            project_updates["segment_assets_prefix"] = assets_prefix

    # payload.status가 있으면 project의 최종 status를 덮어씀 (done, failed 등)
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


async def enqueue_job(job: JobRead, voice_config: Optional[dict] = None) -> None:
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

    message_payload = _build_job_message(job)  # in callback_url
    if voice_config:
        message_payload["voice_config"] = voice_config
    message_body = json.dumps(message_payload)

    message_kwargs: dict[str, Any] = {
        "QueueUrl": JOB_QUEUE_URL,
        "MessageBody": message_body,
        "MessageAttributes": {
            "job_id": {"StringValue": job.job_id, "DataType": "String"},
            "project_id": {"StringValue": job.project_id, "DataType": "String"},
            "task": {
                "StringValue": (job.task or "split_up"),
                "DataType": "String",
            },
        },
    }

    if JOB_QUEUE_FIFO:
        group_id = JOB_QUEUE_MESSAGE_GROUP_ID or job.project_id
        message_kwargs["MessageGroupId"] = group_id
        message_kwargs["MessageDeduplicationId"] = job.job_id

    try:
        response = await asyncio.to_thread(_sqs_client.send_message, **message_kwargs)
    except (BotoCoreError, ClientError) as exc:
        if APP_ENV in {"dev", "development", "local"}:
            logger.error("SQS publish failed in %s env: %s", APP_ENV, exc)
        raise SqsPublishError("Failed to publish job message to SQS") from exc


async def start_jobs_for_targets(
    project: ProjectPublic, target_languages: list[str], db: DbDep
):
    """타겟 언어별로 여러 job을 생성하고 큐에 추가"""
    callback_base = _resolve_callback_base()
    jobs_created = []

    # 프로젝트의 보이스 설정 조회
    voice_config = None
    try:
        project_doc = await db["projects"].find_one(
            {"_id": ObjectId(project.project_id)}
        )
        if project_doc and "voice_config" in project_doc:
            voice_config = project_doc["voice_config"]
    except Exception as exc:
        logger.warning(
            "Failed to load voice_config for project %s: %s", project.project_id, exc
        )

    # 각 타겟 언어에 대해 job 생성
    for target_lang in target_languages:
        job_oid = ObjectId()
        callback_url = f"{callback_base.rstrip('/')}/api/jobs/{job_oid}/status"
        job_payload = JobCreate(
            project_id=project.project_id,
            input_key=project.video_source,
            callback_url=callback_url,
            target_lang=target_lang,  # 타겟 언어 추가
            source_lang=project.source_language,  # 원본 언어 추가
        )

        try:
            job = await create_job(db, job_payload, job_oid=job_oid)
            await enqueue_job(job, voice_config=voice_config)
            jobs_created.append(
                {
                    "project_id": project.project_id,
                    "job_id": job.job_id,
                    "target_lang": target_lang,
                    "status": job.status,
                }
            )
        except (SqsPublishError, Exception) as exc:
            logger.error(
                f"Failed to create/enqueue job for language {target_lang}: {exc}"
            )
            # 실패한 job은 failed로 마킹하지만 다른 언어는 계속 진행
            if isinstance(job_oid, ObjectId):
                await mark_job_failed(
                    db,
                    str(job_oid),
                    error="sqs_publish_failed",
                    message=str(exc),
                )

    if not jobs_created:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to create any jobs",
        )

    return jobs_created


async def start_job(project: ProjectPublic, db: DbDep):
    """단일 job 생성 (기존 호환성 유지)"""
    callback_base = _resolve_callback_base()
    job_oid = ObjectId()
    callback_url = f"{callback_base.rstrip('/')}/api/jobs/{job_oid}/status"

    task_payload = {}
    if project.target_languages:
        task_payload["target_lang"] = project.target_languages[0]

    job_payload = JobCreate(
        project_id=project.project_id,
        input_key=project.video_source,
        callback_url=callback_url,
        task_payload=task_payload if task_payload else None,
        source_lang=project.source_language,  # 원본 언어 추가
    )
    job = await create_job(db, job_payload, job_oid=job_oid)

    # 프로젝트의 보이스 설정 조회
    voice_config = None
    try:
        project_doc = await db["projects"].find_one(
            {"_id": ObjectId(project.project_id)}
        )
        if project_doc and "voice_config" in project_doc:
            voice_config = project_doc["voice_config"]
    except Exception as exc:
        logger.warning(
            "Failed to load voice_config for project %s: %s", project.project_id, exc
        )

    try:
        await enqueue_job(job, voice_config=voice_config)
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


async def start_segment_tts_job(
    db: DbDep,
    *,
    project: dict[str, Any],
    segment_index: int,
    segment: dict[str, Any],
    text: str,
) -> JobRead:
    callback_base = _resolve_callback_base()
    job_oid = ObjectId()
    callback_url = f"{callback_base.rstrip('/')}/api/jobs/{job_oid}/status"

    payload = JobCreate(
        project_id=str(project["_id"]),
        input_key=project.get("video_source"),
        callback_url=callback_url,
        task="segment_tts",
        task_payload=_build_segment_tts_task_payload(
            project,
            segment_index=segment_index,
            segment=segment,
            text=text,
        ),
    )
    job = await create_job(db, payload, job_oid=job_oid)

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

    return job


async def find_full_pipeline_job(
    db: DbDep,
    *,
    project_id: str,
    target_lang: str,
) -> Optional[str]:
    """프로젝트의 full_pipeline job_id를 찾습니다."""
    query = {
        "project_id": project_id,
        "target_lang": target_lang,
        "$or": [
            {"task": "full_pipeline"},
            {"task": "split_up"},
            {"task": None},
            {"task": {"$exists": False}},
        ],
    }

    # 최신 완료된 job을 우선 찾고, 없으면 최신 job 사용
    job_doc = await db[JOB_COLLECTION].find_one(
        query,
        sort=[("created_at", -1)],
    )

    if job_doc:
        return str(job_doc["_id"])
    return None


async def start_segments_tts_job(
    db: DbDep,
    *,
    project_id: str,
    target_lang: str,
    mod: str,
    segments: list[dict[str, Any]],
    voice_sample_id: Optional[str] = None,
    segment_id: Optional[str] = None,  # segment_id 추가 (콜백에서 사용)
) -> JobRead:
    """여러 세그먼트에 대한 TTS 재생성 작업을 큐에 추가합니다."""
    # 프로젝트 정보 조회
    project_doc = await db["projects"].find_one({"_id": ObjectId(project_id)})
    if not project_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # full_pipeline 시 생성된 job_id 찾기
    original_job_id = await find_full_pipeline_job(
        db, project_id=project_id, target_lang=target_lang
    )
    if not original_job_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No full_pipeline job found for project {project_id} with target_lang {target_lang}",
        )

    callback_base = _resolve_callback_base()
    # 새로운 job 생성 (콜백용)
    job_oid = ObjectId()
    callback_url = f"{callback_base.rstrip('/')}/api/jobs/{job_oid}/status"

    # voice_sample_id 또는 speaker_voices에서 speaker_voices 매핑
    resolved_speaker_voices = None
    aws_s3_bucket = os.getenv("AWS_S3_BUCKET")

    # 'clone'은 기본 음성(원본 음성)을 의미하므로 speaker_voices의 default_voice를 사용
    use_default_voice = voice_sample_id == "clone"

    # 1. voice_sample_id가 있고 'clone'이 아니면 해당 voice_sample 사용
    if voice_sample_id and not use_default_voice:
        try:
            from ..voice_samples.service import VoiceSampleService

            voice_sample_service = VoiceSampleService(db)
            voice_sample = await voice_sample_service.get_voice_sample(
                voice_sample_id, None
            )

            # 전처리된 보이스 샘플 우선 사용, 없으면 원본 사용
            voice_key = (
                voice_sample.processed_file_path_wav
                if voice_sample.processed_file_path_wav
                else voice_sample.file_path_wav
            )
            resolved_speaker_voices = {
                "key": voice_key,
            }
            if aws_s3_bucket:
                resolved_speaker_voices["bucket"] = aws_s3_bucket
            if voice_sample.prompt_text:
                resolved_speaker_voices["text_prompt_value"] = voice_sample.prompt_text
        except Exception as exc:
            logger.warning(
                f"Failed to load voice_sample {voice_sample_id}: {exc}. Falling back to speaker_voices."
            )

    # 2. voice_sample_id가 없거나 로드 실패 시 speaker_voices 사용
    if not resolved_speaker_voices:
        speaker_voices = project_doc.get("speaker_voices", {})

        if target_lang in speaker_voices:
            lang_voices = speaker_voices[target_lang]

            if lang_voices:
                # segment_id가 있으면 해당 segment의 speaker_tag로 스피커 찾기
                speaker_key = None
                if segment_id:
                    try:
                        segment_oid = ObjectId(segment_id)
                        segment_doc = await db["project_segments"].find_one(
                            {"_id": segment_oid}
                        )
                        if segment_doc and segment_doc.get("speaker_tag"):
                            speaker_key = segment_doc["speaker_tag"]
                    except Exception:
                        pass

                # speaker_key가 있으면 해당 스피커 사용, 없으면 첫 번째 스피커 사용
                selected_speaker_info = None
                if speaker_key and speaker_key in lang_voices:
                    selected_speaker_info = lang_voices[speaker_key]
                else:
                    selected_speaker_info = next(iter(lang_voices.values()))

                if isinstance(selected_speaker_info, dict):
                    # 'clone'인 경우 default_voice만 사용, 그 외에는 replace_voice 우선 사용
                    voice_info = None
                    if (
                        not use_default_voice
                        and "replace_voice" in selected_speaker_info
                    ):
                        replace_voice = selected_speaker_info["replace_voice"]
                        if (
                            isinstance(replace_voice, dict)
                            and "sample_key" in replace_voice
                        ):
                            voice_info = replace_voice

                    if not voice_info and "default_voice" in selected_speaker_info:
                        voice_info = selected_speaker_info["default_voice"]

                    if (
                        voice_info
                        and isinstance(voice_info, dict)
                        and "ref_wav_key" in voice_info
                    ):
                        resolved_speaker_voices = {
                            "key": voice_info["ref_wav_key"],
                        }
                        if aws_s3_bucket:
                            resolved_speaker_voices["bucket"] = aws_s3_bucket
                        if "prompt_text" in voice_info:
                            resolved_speaker_voices["text_prompt_value"] = voice_info[
                                "prompt_text"
                            ]

    if not resolved_speaker_voices or not resolved_speaker_voices.get("key"):
        logger.error(
            f"❌ [start_segments_tts_job] speaker_voices.key is missing. "
            f"project_id={project_id}, target_lang={target_lang}, "
            f"voice_sample_id={voice_sample_id}, "
            f"speaker_voices={project_doc.get('speaker_voices', {})}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="speaker_voices.key is required. Either provide voice_sample_id or ensure speaker_voices is set for the target language.",
        )

    # segments 형식 변환: { translated_text, start, end } -> { text, s, e }
    worker_segments = []
    for seg in segments:
        worker_segments.append(
            {
                "text": seg.get("translated_text", "").strip(),
                "s": seg.get("start", 0.0),
                "e": seg.get("end"),
                "start": seg.get("start", 0.0),  # 호환성을 위해 둘 다 포함
                "end": seg.get("end"),
                "segment_id": seg.get("segment_id"),
            }
        )

    # task_payload 구성 (original_job_id, segment_id 포함)
    task_payload = {
        "target_lang": target_lang,
        "mod": mod,
        "segments": worker_segments,
        "speaker_voices": resolved_speaker_voices,
        "original_job_id": original_job_id,  # full_pipeline job_id 전달
        "segment_id": segment_id,  # segment_id 추가 (콜백에서 사용) -> 단일일때만
    }

    payload = JobCreate(
        project_id=project_id,
        input_key=project_doc.get("video_source"),
        callback_url=callback_url,
        task="segment_tts",
        task_payload=task_payload,
        target_lang=target_lang,
    )

    job = await create_job(db, payload, job_oid=job_oid)

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

    # 큐잉된 job 데이터 출력
    logger.info(
        f"✅ [start_segments_tts_job] Job queued: job_id={job.job_id}, "
        f"task={job.task}, target_lang={target_lang}, mod={mod}, "
        f"segment_count={len(worker_segments)}, "
        f"speaker_voices_key={resolved_speaker_voices.get('key')}, "
        f"segment_id={segment_id}"
    )

    return job
