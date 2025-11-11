"""
Pytest configuration and fixtures
"""

import pytest
import asyncio
import os
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient
import boto3


@pytest.fixture(scope="session")
def event_loop():
    """이벤트 루프 생성"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db():
    """테스트용 MongoDB 연결"""
    mongo_url = os.getenv("MONGO_URL_DEV", "mongodb://root:example@localhost:27017/dupilot_test?authSource=admin")
    client = AsyncIOMotorClient(mongo_url)
    database = client.get_database()

    yield database

    # 테스트 후 정리
    await database["jobs"].delete_many({})
    await database["projects"].delete_many({})
    await database["project_targets"].delete_many({})
    await database["project_segments"].delete_many({})
    await database["segment_translations"].delete_many({})
    await database["assets"].delete_many({})

    client.close()


@pytest.fixture
async def client():
    """테스트용 HTTP 클라이언트"""
    async with AsyncClient(base_url="http://localhost:8000", timeout=30.0) as ac:
        yield ac


@pytest.fixture(scope="session")
def s3_client():
    """테스트용 S3 클라이언트"""
    aws_profile = os.getenv("AWS_PROFILE")
    aws_region = os.getenv("AWS_REGION", "ap-northeast-2")

    session_kwargs = {}
    if aws_profile:
        session_kwargs["profile_name"] = aws_profile

    session = boto3.Session(**session_kwargs, region_name=aws_region)
    return session.client("s3")


@pytest.fixture
def sample_metadata_json():
    """샘플 메타데이터 JSON"""
    return {
        "v": 1,
        "unit": "ms",
        "lang": "ko",
        "speakers": ["SPEAKER_00"],
        "segments": [
            {
                "s": 217,
                "e": 13426,
                "sp": 0,
                "txt": "좋은 개발자라는 단어가 중요한 단인데 좋은 개발자라고 했을 때 정말 중요한 첫 번째는 기초입니다.",
                "gap": [20, 20],
                "w_off": [0, 22],
                "o": 0,
                "ov": False
            },
            {
                "s": 13446,
                "e": 23187,
                "sp": 0,
                "txt": "빠르게 변하는 거를 이렇게 따라가야 되는데, 그러려면 정말 기초가 탄탄해야 되는 것 같아요.",
                "gap": [None, None],
                "w_off": [22, 17],
                "o": 1,
                "ov": False
            }
        ],
        "vocab": ["좋은", "개발자라는", "단어가"],
        "words": []
    }
