from pathlib import Path
from uuid import uuid4
import json
import asyncio
import os
import logging

from app.config.s3 import s3

logger = logging.getLogger(__name__)
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "dupilot-dev-media")


def build_object_key(project_id: str, file_path: Path) -> str:
    extension = file_path.suffix or ".mp4"
    filename = f"{uuid4()}{extension}"
    return f"projects/{project_id}/inputs/videos/{filename}"


async def download_metadata_from_s3(metadata_key: str) -> dict:
    """
    S3에서 metadata JSON 파일을 다운로드하여 파싱

    지원 포맷:
    - .json: 일반 JSON 파일
    - .json.gz: gzip 압축된 JSON 파일
    - .comp.json.gz: gzip 압축된 JSON 파일 (압축 표시)
    """
    import gzip

    try:
        response = await asyncio.to_thread(
            s3.get_object, Bucket=AWS_S3_BUCKET, Key=metadata_key
        )
        content = await asyncio.to_thread(response["Body"].read)

        # 파일 확장자로 압축 여부 확인
        is_gzipped = metadata_key.endswith(".gz")

        if is_gzipped:
            # gzip 압축 해제
            decompressed = await asyncio.to_thread(gzip.decompress, content)
            metadata = json.loads(decompressed.decode("utf-8"))
        else:
            # 일반 JSON
            metadata = json.loads(content.decode("utf-8"))

        return metadata
    except gzip.BadGzipFile as exc:
        logger.error(f"Failed to decompress gzipped file {metadata_key}: {exc}")
        raise
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse JSON from {metadata_key}: {exc}")
        raise
    except Exception as exc:
        logger.error(f"Failed to download metadata from S3: {exc}")
        raise


def parse_segments_from_metadata(metadata: dict) -> tuple[list[dict], list[str]]:
    """
    메타데이터에서 segments와 translations를 파싱

    입력 포맷 1 (기존 transcript 포맷):
    {
        "v": 1,
        "unit": "ms",
        "lang": "ko",
        "speakers": ["SPEAKER_00"],
        "segments": [
            {
                "s": 217,           # start time (ms)
                "e": 13426,         # end time (ms)
                "sp": 0,            # speaker index
                "txt": "텍스트",    # 원본 텍스트
                ...
            }
        ]
    }

    입력 포맷 2 (새로운 완료 메타데이터 포맷):
    {
        "job_id": "...",
        "project_id": "...",
        "target_lang": "en",
        "segments": [
            {
                "segment_id": "segment_0000",
                "source_duration": 13.194,
                "tts_duration": 5.48,
                "synced_duration": 13.194,
                "audio_file": "..."
            }
        ],
        "translations": [
            {
                "seg_idx": 0,
                "translation": "번역된 텍스트"
            }
        ]
    }

    출력: (segments, translations) 튜플
    """
    # 포맷 감지
    if "translations" in metadata and isinstance(metadata.get("segments"), list):
        # 새로운 포맷 (완료 메타데이터)
        segments_data = metadata.get("segments", [])
        translations_data = metadata.get("translations", [])

        parsed_segments = []
        translations = []

        # translations를 seg_idx로 매핑
        trans_map = {
            t.get("seg_idx", i): t.get("translation", "")
            for i, t in enumerate(translations_data)
        }

        for idx, seg in enumerate(segments_data):
            # segment_id에서 스피커 정보 추출 (예: "SPEAKER_00_0.22.wav"에서)
            audio_file = seg.get("audio_file", "")
            speaker_tag = "SPEAKER_00"  # 기본값
            start_time = 0.0

            if audio_file:
                # 파일명에서 정보 추출 시도
                # 예: "SPEAKER_00_0.22.wav" 또는 "SPEAKER_00_13.43.wav"
                import re

                match = re.search(r"(SPEAKER_\d+)_(\d+\.?\d*)", audio_file)
                if match:
                    speaker_tag = match.group(1)
                    start_time = float(match.group(2))

            # duration을 사용해서 end time 계산
            source_duration = seg.get("source_duration", 0)
            end_time = start_time + source_duration

            segment_record = {
                "segment_index": idx,
                "speaker_tag": speaker_tag,
                "start": start_time,
                "end": end_time,
                "source_text": "",  # 새 포맷에는 원본 텍스트가 없음
                "audio_file": audio_file,  # 추가 정보 보존
            }

            parsed_segments.append(segment_record)

            # 번역 텍스트 추가
            translations.append(trans_map.get(idx, ""))

        return parsed_segments, translations

    else:
        # 기존 포맷 (transcript)
        segments_data = metadata.get("segments", [])
        unit = metadata.get("unit", "ms")  # 시간 단위
        speakers = metadata.get("speakers", [])

        parsed_segments = []

        for idx, seg in enumerate(segments_data):
            # 시간을 초 단위로 변환 (ms -> s)
            start_ms = seg.get("s", 0)
            end_ms = seg.get("e", 0)

            if unit == "ms":
                start_sec = start_ms / 1000.0
                end_sec = end_ms / 1000.0
            else:
                start_sec = float(start_ms)
                end_sec = float(end_ms)

            # speaker 정보 추출
            speaker_idx = seg.get("sp", 0)
            speaker_tag = (
                speakers[speaker_idx]
                if speaker_idx < len(speakers)
                else f"SPEAKER_{speaker_idx}"
            )

            # 원본 텍스트
            source_text = seg.get("txt", "")

            segment_record = {
                "segment_index": idx,
                "speaker_tag": speaker_tag,
                "start": start_sec,
                "end": end_sec,
                "source_text": source_text,
            }

            parsed_segments.append(segment_record)
        return parsed_segments, []  # 기존 포맷은 번역이 없음
