from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middleware.middleware import LoggingMiddleware
from config.env_config import EnvConfig

config = EnvConfig()

app = FastAPI(
    title="My API Gateway",
    description="모든 API 요청의 중앙 진입점",
    version="1.0.0"
)

# 2. CORS 미들웨어 설정 (React 앱의 요청을 허용)
origins = [
    config.get_origins()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # 이 origin들의 요청을 허용
    allow_credentials=True,    # 인증 토큰(JWT) 등을 포함한 요청 허용
    allow_methods=["*"],       # 모든 HTTP 메서드 허용
    allow_headers=["*"]       # 모든 HTTP 헤더 허용
)

app.add_middleware(LoggingMiddleware)

# app.include_router(auth.router, prefix="/api")

# 4. 루트 엔드포인트 (서버 상태 확인용)
@app.get("/", tags=["Status"])
async def read_root():
    return {"status": "API Gateway is running. Visit /docs for API documentation."}

