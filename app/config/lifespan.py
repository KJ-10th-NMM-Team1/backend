from fastapi import FastAPI
from contextlib import asynccontextmanager
from config.db import ensure_db_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_db_connection()
    yield
