import os
import subprocess
import tempfile
from pathlib import Path
from typing import Literal
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError

from app.config.env import settings
from app.config.s3 import s3

ThumbnailFormat = Literal["jpg", "png"]


class ThumbnailError(RuntimeError):
    """Raised when thumbnail extraction or upload fails."""


def _ensure_ffmpeg_available() -> None:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise ThumbnailError("ffmpeg executable is required but not available.") from exc


def extract_thumbnail(
    source_path: str | Path,
    *,
    timestamp: float = 1.0,
    fmt: ThumbnailFormat = "jpg",
) -> Path:
    """
    Extract a single-frame thumbnail from ``source_path``.

    Returns the path to the generated image inside a temporary directory.
    Caller is responsible for deleting the file when done.
    """

    _ensure_ffmpeg_available()

    source = str(source_path)
    tmp_dir = Path(tempfile.mkdtemp(prefix="dupilot-thumb-"))
    output = tmp_dir / f"{uuid4()}.{fmt}"

    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(max(timestamp, 0.0)),
        "-i",
        source,
        "-frames:v",
        "1",
        "-f",
        "image2",
        str(output),
    ]

    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ThumbnailError(f"Failed to extract thumbnail: {exc}") from exc

    if not output.exists():
        raise ThumbnailError("Thumbnail file was not created by ffmpeg.")

    return output


def upload_thumbnail_to_s3(project_id: str, thumbnail_path: Path) -> str:
    """
    Upload ``thumbnail_path`` to S3 under
    ``projects/{project_id}/inputs/thumbnails/`` and return the S3 key.
    """

    bucket = settings.S3_BUCKET
    if not bucket:
        raise ThumbnailError("AWS_S3_BUCKET env not set.")

    object_key = (
        f"projects/{project_id}/inputs/thumbnails/{uuid4()}{thumbnail_path.suffix}"
    )
    extra_args = {"ContentType": f"image/{thumbnail_path.suffix.lstrip('.') or 'jpeg'}"}

    try:
        s3.upload_file(str(thumbnail_path), bucket, object_key, ExtraArgs=extra_args)
    except (BotoCoreError, ClientError) as exc:
        raise ThumbnailError(f"Failed to upload thumbnail: {exc}") from exc

    return object_key


def extract_and_upload_thumbnail(
    source_path: str | Path, project_id: str, *, timestamp: float = 1.0
) -> str:
    """
    Convenience helper that extracts a thumbnail and uploads it to S3,
    returning the resulting S3 key. Cleans up temporary files automatically.
    """

    thumb_path = extract_thumbnail(source_path, timestamp=timestamp)
    try:
        return upload_thumbnail_to_s3(project_id, thumb_path)
    finally:
        try:
            os.remove(thumb_path)
            thumb_path.parent.rmdir()
        except OSError:
            pass
