from fastapi import FastAPI
from settings.db import ensure_db_connection
from api.deps import DbDep
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_db_connection()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def get_main(db: DbDep):
    users = await db["users"].find().to_list()
    print(users)
