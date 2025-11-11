"""
워커 콜백 전체 플로우 통합 테스트

실행: pytest tests/integration/test_worker_callback_flow.py -v
"""

import pytest
from httpx import AsyncClient
from bson import ObjectId
from datetime import datetime


@pytest.mark.asyncio
async def test_full_pipeline_legacy_format(client: AsyncClient, db):
    """전체 파이프라인 테스트 - 기존 포맷 (인라인 segments)"""

    # 1. 프로젝트 생성 (사전 준비 - 실제로는 이미 존재한다고 가정)
    project_id = str(ObjectId())
    await db["projects"].insert_one({
        "_id": ObjectId(project_id),
        "owner_id": ObjectId(),
        "title": "Test Project",
        "video_source": "test.mp4",
        "created_at": datetime.now(),
    })

    # 2. Job 생성
    job_id = str(ObjectId())
    await db["jobs"].insert_one({
        "_id": ObjectId(job_id),
        "project_id": project_id,
        "status": "queued",
        "callback_url": f"http://localhost:8000/api/jobs/{job_id}/status",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "history": [],
    })

    # 3. Project Target 생성
    target_lang = "en"
    await db["project_targets"].insert_one({
        "project_id": project_id,
        "language_code": target_lang,
        "status": "pending",
        "progress": 0,
        "created_at": datetime.now(),
    })

    # 4. 파이프라인 시뮬레이션
    stages = [
        ("starting", 1),
        ("asr_started", 10),
        ("asr_completed", 20),
        ("translation_started", 21),
        ("translation_completed", 35),
        ("tts_started", 36),
        ("tts_completed", 70),
        ("mux_started", 71),
    ]

    for stage, expected_progress in stages:
        response = await client.post(
            f"/api/jobs/{job_id}/status",
            json={
                "status": "in_progress",
                "metadata": {
                    "stage": stage,
                    "target_lang": target_lang,
                }
            }
        )
        assert response.status_code == 200

        # 진행도 확인
        target = await db["project_targets"].find_one({
            "project_id": project_id,
            "language_code": target_lang,
        })
        assert target["progress"] == expected_progress, f"Stage {stage}: expected {expected_progress}, got {target['progress']}"

    # 5. Done 단계 - 세그먼트 및 에셋 생성
    response = await client.post(
        f"/api/jobs/{job_id}/status",
        json={
            "status": "done",
            "result_key": f"projects/{project_id}/output/dubbed_en.mp4",
            "metadata": {
                "stage": "done",
                "target_lang": target_lang,
                "segments": [
                    {
                        "seg_idx": 0,
                        "speaker": "SPEAKER_00",
                        "start": 0.217,
                        "end": 13.426,
                        "prompt_text": "This is the first translated segment",
                        "audio_file": f"projects/{project_id}/segments/0.mp3"
                    },
                    {
                        "seg_idx": 1,
                        "speaker": "SPEAKER_00",
                        "start": 13.446,
                        "end": 23.187,
                        "prompt_text": "This is the second translated segment",
                        "audio_file": f"projects/{project_id}/segments/1.mp3"
                    }
                ]
            }
        }
    )
    assert response.status_code == 200

    # 6. 결과 검증
    # 6.1 Job 상태
    job = await db["jobs"].find_one({"_id": ObjectId(job_id)})
    assert job["status"] == "done"
    assert job["result_key"] == f"projects/{project_id}/output/dubbed_en.mp4"

    # 6.2 Project Target 진행도
    target = await db["project_targets"].find_one({
        "project_id": project_id,
        "language_code": target_lang,
    })
    assert target["progress"] == 100
    assert target["status"] == "completed"

    # 6.3 Segments 생성
    segments = await db["project_segments"].find({"project_id": project_id}).to_list(None)
    assert len(segments) == 2
    assert segments[0]["segment_index"] == 0
    assert segments[0]["source_text"] == "This is the first translated segment"
    assert segments[0]["start"] == 0.217
    assert segments[0]["end"] == 13.426

    # 6.4 Segment Translations 생성
    translations = await db["segment_translations"].find({
        "language_code": target_lang
    }).to_list(None)
    assert len(translations) == 2
    assert translations[0]["target_text"] == "This is the first translated segment"
    assert translations[0]["segment_audio_url"] == f"projects/{project_id}/segments/0.mp3"

    # 6.5 Asset 생성
    assets = await db["assets"].find({"project_id": project_id}).to_list(None)
    assert len(assets) == 1
    assert assets[0]["language_code"] == target_lang
    assert assets[0]["asset_type"] == "dubbed_video"
    assert assets[0]["file_path"] == f"projects/{project_id}/output/dubbed_en.mp4"


@pytest.mark.asyncio
async def test_done_with_metadata_key(client: AsyncClient, db, s3_client):
    """Done 단계 - 새 포맷 (metadata_key 사용)"""

    # 1. 프로젝트 및 Job 준비
    project_id = str(ObjectId())
    job_id = str(ObjectId())
    target_lang = "en"

    await db["projects"].insert_one({
        "_id": ObjectId(project_id),
        "owner_id": ObjectId(),
        "title": "Test Project - New Format",
        "video_source": "test.mp4",
        "created_at": datetime.now(),
    })

    await db["jobs"].insert_one({
        "_id": ObjectId(job_id),
        "project_id": project_id,
        "status": "in_progress",
        "callback_url": f"http://localhost:8000/api/jobs/{job_id}/status",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "history": [],
    })

    await db["project_targets"].insert_one({
        "project_id": project_id,
        "language_code": target_lang,
        "status": "processing",
        "progress": 70,
        "created_at": datetime.now(),
    })

    # 2. S3에 메타데이터 업로드
    import json
    import os

    metadata_key = f"projects/{project_id}/metadata.json"
    s3_metadata = {
        "v": 1,
        "unit": "ms",
        "lang": "ko",
        "speakers": ["SPEAKER_00"],
        "segments": [
            {
                "s": 217,
                "e": 13426,
                "sp": 0,
                "txt": "좋은 개발자라는 단어가 중요합니다.",
            },
            {
                "s": 13446,
                "e": 23187,
                "sp": 0,
                "txt": "빠르게 변하는 기술을 따라가야 합니다.",
            }
        ],
    }

    bucket = os.getenv("AWS_S3_BUCKET", "dupilot-dev-media")
    s3_client.put_object(
        Bucket=bucket,
        Key=metadata_key,
        Body=json.dumps(s3_metadata, ensure_ascii=False),
        ContentType="application/json"
    )

    # 3. Done 콜백 - metadata_key 사용
    response = await client.post(
        f"/api/jobs/{job_id}/status",
        json={
            "status": "done",
            "result_key": f"projects/{project_id}/output/dubbed_en.mp4",
            "metadata": {
                "stage": "done",
                "target_lang": target_lang,
                "metadata_key": metadata_key,
                "translations": [
                    "Good developers are very important.",
                    "We need to keep up with rapidly changing technology."
                ]
            }
        }
    )
    assert response.status_code == 200

    # 4. 결과 검증
    # 4.1 Segments - 원본 텍스트는 S3 메타데이터에서
    segments = await db["project_segments"].find({"project_id": project_id}).to_list(None)
    assert len(segments) == 2
    assert segments[0]["source_text"] == "좋은 개발자라는 단어가 중요합니다."
    assert segments[0]["start"] == pytest.approx(0.217)  # ms -> s 변환
    assert segments[0]["end"] == pytest.approx(13.426)

    # 4.2 Translations - 번역 텍스트는 콜백 metadata에서
    translations = await db["segment_translations"].find({
        "language_code": target_lang
    }).to_list(None)
    assert len(translations) == 2
    assert translations[0]["target_text"] == "Good developers are very important."
    assert translations[1]["target_text"] == "We need to keep up with rapidly changing technology."

    # 4.3 Asset 생성
    assets = await db["assets"].find({"project_id": project_id}).to_list(None)
    assert len(assets) == 1

    # 4.4 S3 정리
    s3_client.delete_object(Bucket=bucket, Key=metadata_key)


@pytest.mark.asyncio
async def test_multiple_languages(client: AsyncClient, db):
    """다중 언어 처리 테스트"""

    project_id = str(ObjectId())
    languages = ["en", "ja", "zh"]

    # 프로젝트 생성
    await db["projects"].insert_one({
        "_id": ObjectId(project_id),
        "owner_id": ObjectId(),
        "title": "Multi-language Project",
        "video_source": "test.mp4",
        "created_at": datetime.now(),
    })

    # 각 언어별 Job 및 처리
    for lang in languages:
        job_id = str(ObjectId())

        await db["jobs"].insert_one({
            "_id": ObjectId(job_id),
            "project_id": project_id,
            "status": "queued",
            "callback_url": f"http://localhost:8000/api/jobs/{job_id}/status",
            "target_lang": lang,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "history": [],
        })

        await db["project_targets"].insert_one({
            "project_id": project_id,
            "language_code": lang,
            "status": "pending",
            "progress": 0,
            "created_at": datetime.now(),
        })

        # Done 단계
        response = await client.post(
            f"/api/jobs/{job_id}/status",
            json={
                "status": "done",
                "result_key": f"projects/{project_id}/output/dubbed_{lang}.mp4",
                "metadata": {
                    "stage": "done",
                    "target_lang": lang,
                    "segments": [
                        {
                            "seg_idx": 0,
                            "speaker": "SPEAKER_00",
                            "start": 0.217,
                            "end": 13.426,
                            "prompt_text": f"Translation in {lang} - segment 1",
                        }
                    ]
                }
            }
        )
        assert response.status_code == 200

    # 검증
    # 1. Segments는 한 번만 생성 (첫 언어에서만)
    segments = await db["project_segments"].find({"project_id": project_id}).to_list(None)
    assert len(segments) == 1

    # 2. 각 언어별 Translations 생성
    for lang in languages:
        translations = await db["segment_translations"].find({
            "language_code": lang
        }).to_list(None)
        assert len(translations) == 1
        assert f"Translation in {lang}" in translations[0]["target_text"]

    # 3. 각 언어별 Asset 생성
    assets = await db["assets"].find({"project_id": project_id}).to_list(None)
    assert len(assets) == 3
    assert set([a["language_code"] for a in assets]) == set(languages)


@pytest.mark.asyncio
async def test_failed_stage(client: AsyncClient, db):
    """실패 단계 처리 테스트"""

    project_id = str(ObjectId())
    job_id = str(ObjectId())
    target_lang = "en"

    await db["projects"].insert_one({
        "_id": ObjectId(project_id),
        "owner_id": ObjectId(),
        "title": "Test Project",
        "created_at": datetime.now(),
    })

    await db["jobs"].insert_one({
        "_id": ObjectId(job_id),
        "project_id": project_id,
        "status": "in_progress",
        "callback_url": f"http://localhost:8000/api/jobs/{job_id}/status",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "history": [],
    })

    await db["project_targets"].insert_one({
        "project_id": project_id,
        "language_code": target_lang,
        "status": "processing",
        "progress": 50,
        "created_at": datetime.now(),
    })

    # Failed 콜백
    response = await client.post(
        f"/api/jobs/{job_id}/status",
        json={
            "status": "failed",
            "error": "ASR processing failed",
            "metadata": {
                "stage": "failed",
                "target_lang": target_lang,
            }
        }
    )
    assert response.status_code == 200

    # 검증
    job = await db["jobs"].find_one({"_id": ObjectId(job_id)})
    assert job["status"] == "failed"
    assert job["error"] == "ASR processing failed"

    target = await db["project_targets"].find_one({
        "project_id": project_id,
        "language_code": target_lang,
    })
    assert target["status"] == "failed"
    assert target["progress"] == 0
