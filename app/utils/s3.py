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
    """S3에서 metadata JSON 파일을 다운로드하여 파싱"""
    try:
        response = await asyncio.to_thread(
            s3.get_object, Bucket=AWS_S3_BUCKET, Key=metadata_key
        )
        content = await asyncio.to_thread(response["Body"].read)
        metadata = json.loads(content.decode("utf-8"))
        logger.info(f"Downloaded metadata from s3://{AWS_S3_BUCKET}/{metadata_key}")
        return metadata
    except Exception as exc:
        logger.error(f"Failed to download metadata from S3: {exc}")
        raise


def parse_segments_from_metadata(metadata: dict) -> list[dict]:
    """
    새로운 metadata 포맷에서 segments를 파싱하여 project_segments 형식으로 변환

    입력 포맷:
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
        ],
        "vocab": [...],
        "words": [...]
    }

    출력 포맷:
    [
        {
            "segment_index": 0,
            "speaker_tag": "SPEAKER_00",
            "start": 0.217,      # 초 단위
            "end": 13.426,       # 초 단위
            "source_text": "텍스트"
        },
        ...
    ]
    """
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
        speaker_tag = speakers[speaker_idx] if speaker_idx < len(speakers) else f"SPEAKER_{speaker_idx}"

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

    logger.info(f"Parsed {len(parsed_segments)} segments from metadata")
    return parsed_segments
