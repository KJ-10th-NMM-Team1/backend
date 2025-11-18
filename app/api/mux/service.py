import os
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional, List
from uuid import uuid4

from pydub import AudioSegment
from botocore.exceptions import ClientError

from app.config.s3 import s3

logger = logging.getLogger(__name__)
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")


def download_from_s3(bucket: str, key: str, local_path: Path) -> bool:
    """S3에서 파일을 다운로드합니다."""
    try:
        logger.info(f"Downloading s3://{bucket}/{key} to {local_path}...")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(bucket, key, str(local_path))
        logger.info(f"Successfully downloaded s3://{bucket}/{key}")
        return True
    except ClientError as e:
        logger.error(f"Failed to download from S3: {e}")
        return False


def upload_to_s3(bucket: str, key: str, local_path: Path) -> bool:
    """S3로 파일을 업로드합니다."""
    try:
        logger.info(f"Uploading {local_path} to s3://{bucket}/{key}...")
        s3.upload_file(str(local_path), bucket, key)
        logger.info(f"Successfully uploaded to s3://{bucket}/{key}")
        return True
    except ClientError as e:
        logger.error(f"Failed to upload to S3: {e}")
        return False
    except FileNotFoundError:
        logger.error(f"Local file not found for upload: {local_path}")
        return False


def mux_audio_video(
    video_path: Path,
    audio_path: Path,
    output_video_path: Path,
) -> dict:
    """
    비디오와 오디오를 결합하여 최종 영상을 생성합니다.

    Args:
        video_path: 원본 비디오 파일 경로
        audio_path: 합성된 오디오 파일 경로
        output_video_path: 출력 비디오 파일 경로

    Returns:
        {"output_video": str, "output_audio": str}
    """
    output_video_path.parent.mkdir(parents=True, exist_ok=True)

    # ffmpeg로 영상의 오디오 트랙을 교체
    cmd = [
        "ffmpeg",
        "-y",  # 덮어쓰기
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "copy",  # 비디오는 재인코딩 없이 복사
        "-map",
        "0:v:0",  # 원본 비디오의 비디오 트랙
        "-map",
        "1:a:0",  # 새 오디오 트랙
        "-shortest",  # 가장 짧은 스트림 길이에 맞춤
        str(output_video_path),
    ]

    subprocess.run(cmd, check=True, timeout=600)  # 10분 타임아웃

    return {
        "output_video": str(output_video_path),
        "output_audio": str(audio_path),
    }


def mux_with_segments(
    video_path: Path,
    background_audio_path: Path,
    segments: List[dict],
    output_audio_path: Path,
    output_video_path: Path,
) -> dict:
    """
    세그먼트 정보를 기반으로 오디오를 믹싱하고 비디오와 결합합니다.

    Args:
        video_path: 원본 비디오 파일 경로
        background_audio_path: 배경음 파일 경로
        segments: 세그먼트 정보 리스트 (각 세그먼트에 audio_file 경로 포함)
        output_audio_path: 출력 오디오 파일 경로
        output_video_path: 출력 비디오 파일 경로

    Returns:
        {"output_video": str, "output_audio": str}
    """
    # 배경 오디오 로드
    background_audio = AudioSegment.from_wav(str(background_audio_path))
    total_duration_ms = len(background_audio)

    # 보컬 합성 결과를 따로 쌓은 뒤 마지막에 배경과 합쳐
    voice_mix = AudioSegment.silent(duration=total_duration_ms)

    # 메타데이터를 기반으로 음성 구간을 정확한 위치에 오버레이
    for segment in segments:
        audio_file_path = Path(segment["audio_file"])
        if not audio_file_path.is_file():
            logger.warning(f"Audio file not found, skipping: {audio_file_path}")
            continue

        segment_audio = AudioSegment.from_wav(str(audio_file_path))

        # 메타데이터에서 정확한 시작 시간 가져오기
        start_time = float(segment.get("start", 0.0))
        start_ms = int(start_time * 1000)

        if start_ms < 0:
            start_ms = 0

        # 해당 위치에 음성 구간을 오버레이
        voice_mix = voice_mix.overlay(segment_audio, position=start_ms)

    # 배경과 음성 레이어를 마지막에 결합
    final_audio = background_audio.overlay(voice_mix, position=0, gain_during_overlay=0)

    # 필요 시 패딩/트리밍으로 길이를 배경 오디오와 동일하게 맞춤
    if len(final_audio) < total_duration_ms:
        silence = AudioSegment.silent(duration=(total_duration_ms - len(final_audio)))
        final_audio = final_audio + silence
    elif len(final_audio) > total_duration_ms:
        final_audio = final_audio[:total_duration_ms]

    # 믹싱된 오디오 저장
    output_audio_path.parent.mkdir(parents=True, exist_ok=True)
    final_audio.export(str(output_audio_path), format="wav")

    # 비디오와 오디오 결합
    return mux_audio_video(video_path, output_audio_path, output_video_path)


async def process_mux(
    project_id: str,
    video_key: str,
    background_audio_key: str,
    segments: List[dict],
    output_prefix: Optional[str] = None,
) -> dict:
    """
    S3에서 파일을 다운로드하여 mux 작업을 수행하고 결과를 업로드합니다.

    Args:
        project_id: 프로젝트 ID
        video_key: 원본 비디오 S3 키
        background_audio_key: 배경음 S3 키
        segments: 세그먼트 정보 리스트, 각 세그먼트는 {
            "start": float,
            "end": float,
            "audio_file": str  # S3 키
        } 형태
        output_prefix: 출력 경로 prefix

    Returns:
        {"result_key": str, "audio_key": str}
    """
    import asyncio

    bucket = AWS_S3_BUCKET

    if not output_prefix:
        output_prefix = f"projects/{project_id}/outputs"

    # 임시 디렉토리 생성
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # S3에서 파일 다운로드
        video_path = temp_path / "video.mp4"
        background_path = temp_path / "background.wav"

        if not download_from_s3(bucket, video_key, video_path):
            raise RuntimeError(f"Failed to download video from S3: {video_key}")

        if not download_from_s3(bucket, background_audio_key, background_path):
            raise RuntimeError(
                f"Failed to download background audio from S3: {background_audio_key}"
            )

        # 각 세그먼트의 오디오 파일 다운로드
        downloaded_segments = []
        for i, seg in enumerate(segments):
            audio_key = seg.get("audio_file")
            if not audio_key:
                logger.warning(f"Segment {i} missing audio_file, skipping")
                continue

            # S3 경로 정규화 (s3://bucket/key 또는 key 형식 모두 지원)
            if audio_key.startswith("s3://"):
                audio_key = audio_key.replace(f"s3://{bucket}/", "")

            seg_audio_path = temp_path / f"segment_{i}.wav"
            if download_from_s3(bucket, audio_key, seg_audio_path):
                seg_copy = dict(seg)
                seg_copy["audio_file"] = str(seg_audio_path)
                downloaded_segments.append(seg_copy)
            else:
                logger.warning(f"Failed to download segment audio: {audio_key}")

        if not downloaded_segments:
            raise ValueError("No valid segments found")

        output_audio_path = temp_path / "dubbed_audio.wav"
        output_video_path = temp_path / "dubbed_video.mp4"

        # 세그먼트 기반 믹싱
        result = await asyncio.to_thread(
            mux_with_segments,
            video_path,
            background_path,
            downloaded_segments,
            output_audio_path,
            output_video_path,
        )

        # 결과물 S3에 업로드
        result_key = f"{output_prefix}/dubbed_video.mp4"
        audio_result_key = f"{output_prefix}/dubbed_audio.wav"

        if not upload_to_s3(bucket, result_key, Path(result["output_video"])):
            raise RuntimeError("Failed to upload result video to S3")

        if Path(result["output_audio"]).exists():
            if not upload_to_s3(bucket, audio_result_key, Path(result["output_audio"])):
                logger.warning("Failed to upload result audio to S3")

        return {
            "result_key": result_key,
            "audio_key": audio_result_key,
        }
