# app/adapters/redis.py
import asyncio
from contextlib import asynccontextmanager
from redis import Redis
from .env import settings


def get_redis() -> Redis:
    return Redis.from_url(settings.REDIS_URL)


@asynccontextmanager
async def distributed_lock(
    lock_name: str,
    timeout: int = 30,
    retry_interval: float = 0.1,
    max_retries: int = 100,
):
    """
    Redis 분산 락 (async context manager)

    Args:
        lock_name: 락 키 이름
        timeout: 락 만료 시간 (초)
        retry_interval: 재시도 간격 (초)
        max_retries: 최대 재시도 횟수
    """
    redis = get_redis()
    lock_key = f"lock:{lock_name}"
    acquired = False

    try:
        # 락 획득 시도
        for _ in range(max_retries):
            # NX: 키가 없을 때만 설정, EX: 만료 시간
            if redis.set(lock_key, "1", nx=True, ex=timeout):
                acquired = True
                break
            await asyncio.sleep(retry_interval)

        if not acquired:
            raise TimeoutError(f"Failed to acquire lock: {lock_name}")

        yield
    finally:
        if acquired:
            redis.delete(lock_key)
