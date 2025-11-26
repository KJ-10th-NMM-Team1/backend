from fastapi import APIRouter
from datetime import datetime
import logging
from bson import ObjectId

from ..deps import DbDep
from .models import JobRead, JobUpdateStatus
from .service import get_job, update_job_status
from ..auth.service import AuthService
from ..auth.model import UserOut
from ..voice_samples.service import VoiceSampleService
from ..voice_samples.models import VoiceSampleUpdate
from ..project.models import ProjectTargetUpdate, ProjectTargetStatus, ProjectUpdate
from ..project.service import ProjectService
from app.utils.project_utils import extract_language_code
from app.utils.speaker_voices import build_speaker_voices_dict


# 새로운 진행도 이벤트 시스템
from ..progress import (
    dispatch_target_progress,
    dispatch_task_completed,
    dispatch_task_failed,
    TaskStatus,
)

from .segment_handler import (
    # check_and_create_segments,
    process_md_completion,
    # tts_complete_processing,
    process_segment_tts_completed,
    process_segment_tts_failed,
    # create_asset_from_result,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/project/{project_id}")
async def get_jobs_by_project(project_id: str, db: DbDep):
    jobs = []
    cursor = db["jobs"].find({"project_id": project_id})
    async for job in cursor:
        # MongoDB의 _id를 id로 변환
        job["id"] = str(job.pop("_id"))
        jobs.append(JobRead(**job))
    return jobs


@router.get("/{job_id}", response_model=JobRead)
async def read_job(job_id: str, db: DbDep) -> JobRead:
    return await get_job(db, job_id)


# ============================================================================
# 모든 헬퍼 함수들은 event_dispatcher.py와 segment_handler.py로 이동되었습니다
# ============================================================================


@router.post("/{job_id}/status", response_model=JobRead)
async def set_job_status(job_id: str, payload: JobUpdateStatus, db: DbDep) -> JobRead:
    # job 상태 업데이트
    result = await update_job_status(db, job_id, payload)

    metadata = None
    if payload.metadata is not None:
        if payload.metadata is not None:
            metadata = (
                payload.metadata.model_dump()
                if hasattr(payload.metadata, "model_dump")
                else payload.metadata
            )
    # voice_sample_id가 있으면 audio_sample_url 업데이트
    if metadata and "voice_sample_id" in metadata:
        if result.status == "done":
            voice_sample_id = metadata["voice_sample_id"]
            try:
                service = VoiceSampleService(db)

                # 샘플을 직접 DB에서 조회 (owner_id만 필요)
                try:
                    sample_oid = ObjectId(voice_sample_id)
                    sample_doc = await service.collection.find_one({"_id": sample_oid})
                    if sample_doc:
                        # owner_id로 사용자 조회
                        auth_service = AuthService(db)
                        owner_oid = sample_doc["owner_id"]
                        user_doc = await auth_service.collection.find_one(
                            {"_id": owner_oid}
                        )
                        if user_doc:
                            owner = UserOut(**user_doc)
                            # 업데이트할 데이터 구성
                            update_data = {}

                            # audio_sample_url 업데이트 (워커에서 보낸 값 우선, 없으면 result_key로 생성)
                            audio_sample_url = metadata.get("audio_sample_url")
                            if not audio_sample_url and result.result_key:
                                audio_sample_url = (
                                    f"/api/storage/media/{result.result_key}"
                                )

                            if audio_sample_url:
                                update_data["audio_sample_url"] = audio_sample_url

                            # prompt_text 업데이트
                            prompt_text = metadata.get("prompt_text")
                            if prompt_text:
                                update_data["prompt_text"] = prompt_text

                            # processed_file_path_wav 업데이트 (전처리된 보이스 샘플)
                            sample_key = metadata.get("sample_key")
                            if sample_key:
                                update_data["processed_file_path_wav"] = sample_key

                            if update_data:
                                await service.update_voice_sample(
                                    voice_sample_id,
                                    VoiceSampleUpdate(**update_data),
                                    owner,
                                )

                except Exception as owner_exc:
                    logger.error(
                        f"Failed to get owner for voice sample {voice_sample_id}: {owner_exc}"
                    )
            except Exception as exc:
                logger.error(
                    f"Failed to update audio_sample_url for voice sample {voice_sample_id}: {exc}"
                )

    # state 없을 때 리턴
    if not metadata or "stage" not in metadata:
        return result

    stage = metadata["stage"]
    project_id = result.project_id

    print(f"metadata for job {job_id}, stage {stage}: {metadata}")

    # metadata에서 language_code 추출 (target_lang)
    language_code = metadata.get("target_lang") or metadata.get("language_code")

    # 특정 stage에서는 language_code가 필요하지 않을 수 있음
    language_independent_stages = ["downloaded", "stt_completed"]

    if not language_code and stage not in language_independent_stages:
        logger.warning(f"No target_lang in metadata for job {job_id}, stage {stage}")
        # language_code가 없는 경우, project의 첫 번째 target language 사용 시도
        try:
            project_service = ProjectService(db)
            targets = await project_service.get_targets_by_project(project_id)
            if targets and len(targets) > 0:
                # 유틸 함수로 첫 번째 타겟의 언어 코드 추출
                language_code = extract_language_code(targets[0])

        except Exception as exc:
            logger.error(f"Failed to get project targets: {exc}")

    if not language_code and stage not in language_independent_stages:
        logger.error(f"Cannot determine language_code for job {job_id}, stage {stage}")
        return result

    # ProjectService 인스턴스 생성
    project_service = ProjectService(db)

    # 프로젝트 정보 조회 (제목 가져오기)
    project_title = None
    try:
        project_doc = await db["projects"].find_one({"_id": ObjectId(project_id)})
        if project_doc:
            project_title = project_doc.get("title")
    except Exception as exc:
        logger.warning(f"Failed to get project title: {exc}")

    # stage별 project_target 업데이트를 위한 payload
    target_update = None

    # stage별, project target 업데이트
    if stage == "starting":  # s3에서 불러오기 완료 (stt 시작)
        target_update = ProjectTargetUpdate(
            status=ProjectTargetStatus.PROCESSING, progress=1
        )
    elif stage == "asr_started":  # stt 시작
        target_update = ProjectTargetUpdate(
            status=ProjectTargetStatus.PROCESSING, progress=5  # STT 시작 시 5%
        )
    elif stage == "asr_completed":  # stt 완료
        # 원본 오디오, 발화 음성, 배경음, 오디오 제거 비디오 경로를 프로젝트에 저장
        if metadata:
            audio_key = metadata.get("audio_key")  # 원본 오디오 (mp4->wav)
            vocals_key = metadata.get("vocals_key")  # 발화 음성 (vocals.wav)
            background_key = metadata.get("background_key")  # 배경음

            if audio_key or vocals_key or background_key:
                update_data = {}

                if audio_key:
                    update_data["audio_source"] = audio_key  # 원본 오디오

                if vocals_key:
                    update_data["vocal_source"] = vocals_key  # 발화 음성

                if background_key:
                    update_data["background_audio_source"] = background_key

                if update_data:
                    try:
                        await project_service.update_project(
                            ProjectUpdate(project_id=project_id, **update_data)
                        )
                        logger.info(
                            f"Updated project {project_id} with audio/video files: "
                            f"audio_source={update_data.get('audio_source', 'N/A')}, "
                            f"vocal_source={update_data.get('vocal_source', 'N/A')}, "
                        )
                    except Exception as exc:
                        logger.error(
                            f"Failed to update project audio/video files: {exc}"
                        )

        target_update = ProjectTargetUpdate(
            status=ProjectTargetStatus.PROCESSING, progress=20
        )
    elif stage == "translation_started":
        target_update = ProjectTargetUpdate(
            status=ProjectTargetStatus.PROCESSING, progress=21
        )
    elif stage == "translation_completed":  # mt 완료
        target_update = ProjectTargetUpdate(
            status=ProjectTargetStatus.PROCESSING, progress=35
        )
    elif stage == "tts_started":  # TTS 시작
        target_update = ProjectTargetUpdate(
            status=ProjectTargetStatus.PROCESSING, progress=36
        )
    elif stage == "tts_completed":  # TTS 완료
        # speaker_voices를 새로운 구조로 변환하여 프로젝트에 저장
        if metadata and language_code:
            try:
                speakers_list = metadata.get("speakers", [])
                speaker_refs = metadata.get("speaker_refs")
                voice_replacements = None  # tts_completed에서는 voice_replacements가 metadata에 직접 포함되지 않을 수 있음

                # 유틸 함수를 사용하여 speaker_voices_dict 생성
                speaker_voices_dict = build_speaker_voices_dict(
                    speakers_list=speakers_list,
                    speaker_refs=speaker_refs,
                    voice_replacements=voice_replacements,
                )

                if speaker_voices_dict:
                    # 기존 speaker_voices 가져오기
                    project_oid = ObjectId(project_id)
                    project_doc = await db["projects"].find_one({"_id": project_oid})
                    existing_speaker_voices = (
                        project_doc.get("speaker_voices", {}) if project_doc else {}
                    )

                    # 새로운 언어 데이터 추가 (기존 데이터 유지)
                    updated_speaker_voices = {
                        **existing_speaker_voices,
                        language_code: speaker_voices_dict,
                    }

                    await project_service.update_project(
                        ProjectUpdate(
                            project_id=project_id,
                            speaker_voices=updated_speaker_voices,
                        )
                    )
                    logger.info(
                        f"Updated project {project_id} with speaker_voices for language {language_code}"
                    )
            except Exception as exc:
                logger.error(
                    f"Failed to update speaker_voices for project {project_id}: {exc}",
                    exc_info=True,
                )

        target_update = ProjectTargetUpdate(
            status=ProjectTargetStatus.PROCESSING, progress=85  # TTS 완료 시 85%
        )
    elif stage == "segment_tts_completed":  # 세그먼트 TTS 재생성 완료
        if metadata and language_code:
            await process_segment_tts_completed(db, project_id, language_code, metadata)

    elif stage == "segment_tts_failed":  # 세그먼트 TTS 재생성 실패
        # 실패 이벤트 발송
        if metadata and language_code:
            await process_segment_tts_failed(db, project_id, language_code, metadata)

    elif stage == "mux_started":  # 비디오 처리 시작
        target_update = ProjectTargetUpdate(
            status=ProjectTargetStatus.PROCESSING,
            progress=86,  # 비디오 처리 시작 시 86%
        )
    elif stage == "done":  # 비디오 처리 완료
        # speaker_refs 또는 speakers가 있으면 저장 (tts_completed를 건너뛴 경우 대비)
        if metadata and language_code:
            speakers_list = metadata.get("speakers") or []
            speaker_refs = metadata.get("speaker_refs") or {}
            # voice_replacements는 speakers_list에 이미 포함되어 있을 수 있음
            # 또는 별도로 전달될 수도 있음 (현재는 speakers_list에 포함된 것으로 가정)

            # speakers 또는 speaker_refs에서 정보 추출
            if speakers_list or speaker_refs:
                try:
                    # 유틸 함수를 사용하여 speaker_voices_dict 생성
                    speaker_voices_dict = build_speaker_voices_dict(
                        speakers_list=speakers_list,
                        speaker_refs=speaker_refs,
                        voice_replacements=None,  # speakers_list에 이미 포함되어 있음
                    )

                    if speaker_voices_dict:
                        # 기존 speaker_voices 가져오기
                        project_oid = ObjectId(project_id)
                        project_doc = await db["projects"].find_one(
                            {"_id": project_oid}
                        )
                        existing_speaker_voices = (
                            project_doc.get("speaker_voices", {}) if project_doc else {}
                        )

                        # 새로운 언어 데이터 추가 (기존 데이터 유지)
                        updated_speaker_voices = {
                            **existing_speaker_voices,
                            language_code: speaker_voices_dict,
                        }

                        await project_service.update_project(
                            ProjectUpdate(
                                project_id=project_id,
                                speaker_voices=updated_speaker_voices,
                            )
                        )

                except Exception as exc:
                    logger.error(
                        f"❌ [done] Failed to update speaker_voices for project {project_id}: {exc}",
                        exc_info=True,
                    )

        # 새로운 처리 함수 호출: asset 생성 및 세그먼트 생성
        # result_key는 metadata 또는 result에서 가져옴
        final_result_key = metadata.get("result_key") or result.result_key

        await process_md_completion(
            db, project_id, metadata, final_result_key, defaultTarget=language_code
        )

        target_update = ProjectTargetUpdate(
            status=ProjectTargetStatus.COMPLETED,
            progress=100,  # 비디오 처리 완료 시 100%
        )
    elif stage == "failed":  # 실패
        target_update = ProjectTargetUpdate(
            status=ProjectTargetStatus.FAILED, progress=0
        )

    print(f"target_lang for job {job_id}, stage {stage}: {language_code}")

    # project_target 업데이트 실행
    if target_update:
        try:
            # language_code가 있으면 해당 언어만 업데이트
            if language_code:
                # 현재 target 상태 확인 - 이미 COMPLETED면 업데이트 건너뛰기
                current_targets = await project_service.get_targets_by_project(
                    project_id, language_code
                )
                if current_targets and len(current_targets) > 0:
                    current_target = current_targets[0]
                    if current_target.status == ProjectTargetStatus.COMPLETED:
                        logger.info(
                            f"Skipping target update for project {project_id}, "
                            f"language {language_code}: already COMPLETED (incoming stage: {stage})"
                        )
                        return result

                await project_service.update_targets_by_project_and_language(
                    project_id, language_code, target_update
                )

                # 새로운 진행도 이벤트 시스템으로 브로드캐스트
                await dispatch_target_progress(
                    project_id=project_id,
                    target_lang=language_code,
                    stage=stage,
                    status=(
                        TaskStatus.COMPLETED
                        if stage == "done"
                        else (
                            TaskStatus.FAILED
                            if stage == "failed"
                            else TaskStatus.PROCESSING
                        )
                    ),
                    progress=target_update.progress or 0,
                    message=f"Stage: {stage}",
                    db=db,  # DB 전달하여 전체 진행도 자동 계산
                    project_title=project_title,  # 프로젝트 제목 전달
                )

        except Exception as exc:
            logger.error(f"Failed to update project_target: {exc}")

    return result
