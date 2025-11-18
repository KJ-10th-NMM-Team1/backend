import os
import asyncio
import tempfile
import logging
from pathlib import Path
from typing import Optional

from app.config.s3 import s3 as s3_client

logger = logging.getLogger(__name__)
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "dupilot-dev-media")


def ffprobe_duration_sync(file_path: str) -> float:
    """오디오 파일의 길이(초)를 반환 (동기)"""
    import subprocess

    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    except Exception as exc:
        logger.error(f"Failed to get audio duration: {exc}")
        raise


async def get_audio_duration_from_s3(s3_key: str) -> Optional[float]:
    """
    S3에서 오디오 파일을 다운로드하여 duration을 구합니다.

    Args:
        s3_key: S3 객체 키

    Returns:
        오디오 길이(초), 실패 시 None
    """
    if not s3_key:
        logger.warning("s3_key is empty")
        return None

    tmp_path = None
    try:
        # S3에서 파일 존재 확인
        try:
            await asyncio.to_thread(
                s3_client.head_object,
                Bucket=AWS_S3_BUCKET,
                Key=s3_key,
            )
        except Exception as exc:
            logger.error(f"S3 file not found: {s3_key}, error: {exc}")
            return None

        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_path = Path(tmp_file.name)

        # S3에서 파일 다운로드
        response = await asyncio.to_thread(
            s3_client.get_object,
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
        )

        # 파일 저장
        with open(tmp_path, "wb") as f:
            for chunk in response["Body"].iter_chunks(chunk_size=8192):
                f.write(chunk)

        # ffprobe로 duration 구하기
        duration = await asyncio.to_thread(ffprobe_duration_sync, str(tmp_path))
        return duration

    except Exception as exc:
        logger.error(f"Failed to get audio duration from S3: {s3_key}, error: {exc}")
        return None

    finally:
        # 임시 파일 정리
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception as exc:
                logger.warning(f"Failed to delete temp file {tmp_path}: {exc}")


async def download_audio_from_s3(s3_key: str) -> Optional[Path]:
    """
    S3에서 오디오 파일을 다운로드하여 임시 파일로 저장합니다.

    Args:
        s3_key: S3 객체 키

    Returns:
        임시 파일 경로, 실패 시 None
    """
    if not s3_key:
        logger.warning("s3_key is empty")
        return None

    try:
        # S3에서 파일 존재 확인
        await asyncio.to_thread(
            s3_client.head_object,
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
        )

        # 임시 파일 생성
        suffix = Path(s3_key).suffix or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_path = Path(tmp_file.name)

        # S3에서 파일 다운로드
        response = await asyncio.to_thread(
            s3_client.get_object,
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
        )

        # 파일 저장
        with open(tmp_path, "wb") as f:
            for chunk in response["Body"].iter_chunks(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Downloaded audio from S3: {s3_key} -> {tmp_path}")
        return tmp_path

    except Exception as exc:
        logger.error(f"Failed to download audio from S3: {s3_key}, error: {exc}")
        return None


def split_audio_with_ffmpeg(
    input_path: str, output_path1: str, output_path2: str, split_time: float
) -> tuple[bool, str]:
    """
    FFmpeg를 사용하여 오디오 파일을 두 부분으로 분할합니다.

    Args:
        input_path: 입력 오디오 파일 경로
        output_path1: 첫 번째 출력 파일 경로 (0 ~ split_time)
        output_path2: 두 번째 출력 파일 경로 (split_time ~ 끝)
        split_time: 분할 시점 (초)

    Returns:
        (성공 여부, 에러 메시지)
    """
    import subprocess

    try:
        # Part 1: 0 ~ split_time
        cmd1 = [
            "ffmpeg",
            "-i",
            input_path,
            "-t",
            str(split_time),
            "-acodec",
            "copy",
            "-y",
            output_path1,
        ]
        result1 = subprocess.run(
            cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result1.returncode != 0:
            return False, f"Failed to create part1: {result1.stderr}"

        # Part 2: split_time ~ 끝
        cmd2 = [
            "ffmpeg",
            "-i",
            input_path,
            "-ss",
            str(split_time),
            "-acodec",
            "copy",
            "-y",
            output_path2,
        ]
        result2 = subprocess.run(
            cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result2.returncode != 0:
            return False, f"Failed to create part2: {result2.stderr}"

        logger.info(f"Successfully split audio at {split_time}s")
        return True, ""

    except Exception as exc:
        logger.error(f"Failed to split audio with ffmpeg: {exc}")
        return False, str(exc)


async def upload_audio_to_s3(file_path: Path, s3_key: str) -> bool:
    """
    로컬 오디오 파일을 S3에 업로드합니다.

    Args:
        file_path: 업로드할 파일 경로
        s3_key: S3 객체 키

    Returns:
        성공 여부
    """
    try:
        with open(file_path, "rb") as f:
            await asyncio.to_thread(
                s3_client.put_object,
                Bucket=AWS_S3_BUCKET,
                Key=s3_key,
                Body=f,
                ContentType="audio/wav",
            )
        logger.info(f"Uploaded audio to S3: {file_path} -> {s3_key}")
        return True

    except Exception as exc:
        logger.error(f"Failed to upload audio to S3: {s3_key}, error: {exc}")
        return False


def merge_audio_with_ffmpeg(
    input_paths: list[str], output_path: str
) -> tuple[bool, str]:
    """
    FFmpeg를 사용하여 여러 오디오 파일을 하나로 병합합니다.

    Args:
        input_paths: 입력 오디오 파일 경로 리스트 (순서대로 병합됨)
        output_path: 출력 파일 경로

    Returns:
        (성공 여부, 에러 메시지)
    """
    import subprocess

    if not input_paths:
        return False, "No input files provided"

    if len(input_paths) == 1:
        # 파일이 하나만 있으면 복사
        try:
            import shutil
            shutil.copy(input_paths[0], output_path)
            return True, ""
        except Exception as exc:
            return False, str(exc)

    filelist_path = None
    try:
        # FFmpeg concat demuxer를 위한 파일 목록 생성
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".txt"
        ) as filelist:
            filelist_path = Path(filelist.name)
            for input_path in input_paths:
                # 경로에 특수문자가 있을 수 있으므로 이스케이프
                escaped_path = str(input_path).replace("'", "'\\''")
                filelist.write(f"file '{escaped_path}'\n")

        # FFmpeg concat demuxer로 병합
        cmd = [
            "ffmpeg",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(filelist_path),
            "-c",
            "copy",
            "-y",
            output_path,
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode != 0:
            return False, f"FFmpeg merge failed: {result.stderr}"

        logger.info(f"Successfully merged {len(input_paths)} audio files")
        return True, ""

    except Exception as exc:
        logger.error(f"Failed to merge audio with ffmpeg: {exc}")
        return False, str(exc)

    finally:
        # 파일 목록 임시 파일 정리
        if filelist_path and filelist_path.exists():
            try:
                filelist_path.unlink()
            except Exception as exc:
                logger.warning(f"Failed to delete filelist {filelist_path}: {exc}")
