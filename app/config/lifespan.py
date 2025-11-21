from fastapi import FastAPI
import logging
from contextlib import asynccontextmanager
from app.config.db import ensure_db_connection, ensure_indexes

# from app.api.translate.service import vector_search

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_db_connection()
    await ensure_indexes()
    # Glossary warmup disabled
    yield
