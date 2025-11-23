import os, boto3
from dotenv import load_dotenv
from .env import settings

load_dotenv()


aws_profile = os.getenv("AWS_PROFILE")
aws_region = os.getenv("AWS_REGION", "ap-northeast-2")

session_kwargs = {}
if aws_profile:
    session_kwargs["profile_name"] = aws_profile

session = boto3.Session(**session_kwargs, region_name=aws_region)
s3 = session.client("s3")


def drop_projects(project_id):
    bucket = settings.S3_BUCKET
    prefix = f"projects/{project_id}/"
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        objects = page.get("Contents", [])
        if not objects:
            continue
        delete_payload = {
            "Objects": [{"Key": obj["Key"]} for obj in objects],
            "Quiet": True,
        }
        s3.delete_objects(Bucket=bucket, Delete=delete_payload)


def drop_voice_sample_keys(keys: list[str]):
    """지정된 S3 키 리스트를 삭제"""
    bucket = settings.S3_BUCKET
    if not keys:
        return

    delete_payload = {
        "Objects": [{"Key": key} for key in keys],
        "Quiet": True,
    }
    s3.delete_objects(Bucket=bucket, Delete=delete_payload)


def drop_voice_sample(user_id: str, sample_id: str, file_keys: list[str] | None = None):
    """
    음성 샘플 삭제: 명시된 S3 키 목록(file_keys)을 우선 삭제.
    file_keys가 없으면 업로드 키 패턴 접두어로 정리 (voice-samples/{user_id}/{sample_id}_).
    """
    bucket = settings.S3_BUCKET
    # 1) 명시된 파일 키가 있으면 그 리스트로 삭제
    if file_keys:
        drop_voice_sample_keys(file_keys)
        return

    # 2) fallback: sample_id 기반 접두어로 삭제
    prefix = f"voice-samples/{user_id}/{sample_id}_"
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        objects = page.get("Contents", [])
        if not objects:
            continue
        delete_payload = {
            "Objects": [{"Key": obj["Key"]} for obj in objects],
            "Quiet": True,
        }
        s3.delete_objects(Bucket=bucket, Delete=delete_payload)
