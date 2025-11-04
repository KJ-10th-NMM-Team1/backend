from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from pymongo import ReturnDocument

from ..deps import DbDep
from .models import TranslatorCreate, TranslatorOut, TranslatorStatus, TranslatorUpdate

translator_router = APIRouter(prefix="/translators", tags=["translators"])


def _serialize(doc: dict) -> TranslatorOut:
    return TranslatorOut.model_validate(doc)


@translator_router.post(
    "/",
    response_model=TranslatorOut,
    status_code=status.HTTP_201_CREATED,
    summary="번역가 등록",
)
async def create_translator(payload: TranslatorCreate, db: DbDep) -> TranslatorOut:
    if await db["translators"].find_one({"email": payload.email}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
        )

    now = datetime.utcnow()
    doc = payload.model_dump()
    doc["created_at"] = now
    doc["updated_at"] = now

    result = await db["translators"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


@translator_router.get(
    "/",
    response_model=list[TranslatorOut],
    summary="번역가 목록 조회",
)
async def list_translators(
    db: DbDep,
    status_filter: TranslatorStatus | None = None,
) -> list[TranslatorOut]:
    query: dict[str, object] = {}
    if status_filter:
        query["status"] = status_filter.value

    docs = (
        await db["translators"].find(query).sort("created_at", -1).to_list(length=None)
    )
    return [_serialize(doc) for doc in docs]


@translator_router.get(
    "/{translator_id}",
    response_model=TranslatorOut,
    summary="번역가 상세 조회",
)
async def get_translator(translator_id: str, db: DbDep) -> TranslatorOut:
    try:
        oid = ObjectId(translator_id)
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid translator_id"
        ) from exc

    doc = await db["translators"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Translator not found"
        )

    return _serialize(doc)


@translator_router.put(
    "/{translator_id}",
    response_model=TranslatorOut,
    summary="번역가 정보 수정",
)
async def update_translator(
    translator_id: str,
    payload: TranslatorUpdate,
    db: DbDep,
) -> TranslatorOut:
    try:
        oid = ObjectId(translator_id)
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid translator_id"
        ) from exc

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No update fields provided"
        )

    if "email" in updates:
        duplicate = await db["translators"].find_one(
            {"email": updates["email"], "_id": {"$ne": oid}}
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
            )

    updates["updated_at"] = datetime.utcnow()

    doc = await db["translators"].find_one_and_update(
        {"_id": oid},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Translator not found"
        )

    return _serialize(doc)


@translator_router.delete(
    "/{translator_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="번역가 삭제",
)
async def delete_translator(translator_id: str, db: DbDep) -> Response:
    try:
        oid = ObjectId(translator_id)
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid translator_id"
        ) from exc

    result = await db["translators"].delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Translator not found"
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
