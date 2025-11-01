from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.middleware import LoggingMiddleware
from app.config.env_config import EnvConfig
from app.api.deps import DbDep
from app.config.lifespan import lifespan
from app.api.main import api_router

config = EnvConfig()

app = FastAPI(
    title="Dupilot",
    description="영상 더빙 API",
    version="0.0.1",
    lifespan=lifespan,
)

# 2. CORS 미들웨어 설정 (React 앱의 요청을 허용)
origins = [config.get_origins()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 이 origin들의 요청을 허용
    allow_credentials=True,  # 인증 토큰(JWT) 등을 포함한 요청 허용
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 HTTP 헤더 허용
)

app.add_middleware(LoggingMiddleware)

app.include_router(api_router)


# 4. 루트 엔드포인트 (서버 상태 확인용)
@app.get("/", tags=["Status"])
async def read_root(db: DbDep):
    users = await db["users"].find().to_list()
    print(users)
    return {"status": "API Gateway is running. Visit /docs for API documentation."}
