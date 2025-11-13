from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.middleware import LoggingMiddleware
from app.config.env import origins as allowed_origins
from app.api.deps import DbDep
from app.config.lifespan import lifespan
from app.api.main import api_router

app = FastAPI(
    title="Dupilot",
    description="영상 더빙 API",
    version="0.0.1",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LoggingMiddleware)

app.include_router(api_router)


# 4. 루트 엔드포인트 (서버 상태 확인용)
@app.get("/", tags=["Status"])
async def read_root(db: DbDep):
    users = await db["users"].find().to_list()
    return {"status": "API Gateway is running. Visit /docs for API documentation."}
