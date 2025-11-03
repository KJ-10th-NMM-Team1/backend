#  service 테스트용 api
from fastapi import APIRouter
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from ..deps import DbDep
from .service import glosary_suggestion

trans_router = APIRouter(prefix="/trans", tags=["translate"])


@trans_router.post("/test")
async def test_set_seg(db: DbDep):
    await db["segments"].insert_one(
        {
            "segment_text": "첫 번째 원문 텍스트입니다.",
            "translate_text": "This is the first original text.",
        }
    )


@trans_router.post("/glossary-suggestion")
async def get_glosary_suggestion(db: DbDep, segment_id: str):
    try:
        segment_oid = ObjectId(segment_id)
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid segment_id",
        ) from exc

    review = await glosary_suggestion(db, segment_oid)

    return {"segment_id": str(segment_oid), "review": review}
