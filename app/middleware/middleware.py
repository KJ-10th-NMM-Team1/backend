import logging
import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

# 'api_logger'라는 이름의 로거 생성
logger = logging.getLogger("api_logger")
logger.setLevel(logging.INFO)
# 로그 포맷 설정 (시간 - 로거이름 - 레벨 - 메시지)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        client_ip = request.client.host
        method = request.method
        path = request.url.path

        # (중요) 실제 엔드포인트 실행
        response = await call_next(request)

        # --- (2) 응답 처리 후 ---
        process_time = time.time() - start_time
        status_code = response.status_code

        # 응답 로그 (처리 시간과 상태 코드를 포함)
        logger.info(f"Response: {status_code} | Process Time: {process_time:.4f}s")

        return response
