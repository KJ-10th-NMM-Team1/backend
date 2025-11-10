import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, status

AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")


MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
MAX_DURATION = 60  # 60초


def ffprobe_duration(file_path: str) -> float:
    """오디오 파일의 길이(초)를 반환"""
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get audio duration: {exc}",
        ) from exc


def validate_audio_file_info(
    filename: str, content_type: str, file_size: Optional[int] = None
) -> None:
    """오디오 파일 정보 검증 (크기, 형식)"""
    # 파일 크기 검증
    if file_size and file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="20MB 이하의 파일만 업로드할 수 있습니다.",
        )

    # 파일 형식 검증
    if not (
        content_type.startswith("audio/") or filename.lower().endswith((".mp3", ".wav"))
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mp3 또는 wav 파일만 업로드할 수 있습니다.",
        )


async def validate_audio_file_from_s3(object_key: str) -> float:
    """
    S3에 업로드된 오디오 파일 검증 (존재, 크기, 길이)
    - 파일 존재 확인 (HEAD 요청)
    - 파일 크기 검증 (20MB 이하)
    - 파일 길이 검증 (60초 이내) - Range 요청으로 일부만 다운로드
    - 반환: 길이(초)
    """
    if not AWS_S3_BUCKET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AWS_S3_BUCKET not configured",
        )

    try:
        import asyncio
        from app.config.s3 import s3 as s3_client
        from botocore.exceptions import ClientError

        # S3 HEAD 요청으로 파일 존재 및 메타데이터 확인
        try:
            response = await asyncio.to_thread(
                s3_client.head_object,
                Bucket=AWS_S3_BUCKET,
                Key=object_key,
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="업로드된 파일을 찾을 수 없습니다.",
                )
            raise

        # 파일 크기 검증
        file_size = response.get("ContentLength", 0)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="20MB 이하의 파일만 업로드할 수 있습니다.",
            )

        # 파일 길이 검증: Range 요청으로 처음 1MB만 다운로드 (메타데이터 포함)
        # 대부분의 오디오 포맷은 헤더에 길이 정보가 있음
        range_size = min(1024 * 1024, file_size)  # 1MB 또는 파일 크기 중 작은 값

        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            # Range 요청으로 파일의 일부만 다운로드
            range_response = await asyncio.to_thread(
                s3_client.get_object,
                Bucket=AWS_S3_BUCKET,
                Key=object_key,
                Range=f"bytes=0-{range_size - 1}",
            )

            # 다운로드한 데이터를 임시 파일에 저장
            with open(tmp_path, "wb") as f:
                for chunk in range_response["Body"].iter_chunks(chunk_size=8192):
                    f.write(chunk)

            # ffprobe로 길이 확인 (헤더만 읽어도 길이를 알 수 있음)
            duration = ffprobe_duration(str(tmp_path))
            if duration > MAX_DURATION:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="60초 이내의 파일만 업로드할 수 있습니다.",
                )

            return duration

        finally:
            # 임시 파일 정리
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"파일 검증 중 오류 발생: {exc}",
        ) from exc
