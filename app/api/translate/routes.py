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
            "project_id": ObjectId("69083650141e52c49d637523"),
            "segment_text": "The new graphics card launch was insane, no way! Oh my gosh, Rosie, your album finally dropped on Jimmy Fallon's show",
            "translate_context": "새 지피유 는 미쳤어, 길이없다! 오 마이 갓, 로지 너의 앨범이 드디어 지미펠런의 쇼에 떨어졌어",
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
