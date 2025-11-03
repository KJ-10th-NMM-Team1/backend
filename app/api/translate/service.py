import re
from dotenv import load_dotenv
from datetime import datetime
from fastapi import HTTPException, status
from bson import ObjectId
from bson.errors import InvalidId
from .rag import rag_glossary_correction
from .utils import vector_search

from ..deps import DbDep

load_dotenv()


def detect_glossary_issues(source: str, mt: str, top_k: int = 5):
    query = f"{source.strip()}\n\n{mt.strip()}"
    hits = vector_search(query, top_k)

    issues: list[str] = []
    suggestion = mt

    for hit in hits:
        raw = hit.raw
        preferred = (raw.get("preferred") or "").strip()
        term = (raw.get("term") or "").strip()
        aliases = [a.strip() for a in raw.get("aliases", []) if a.strip()]
        forbidden = [w.strip() for w in raw.get("forbidden", []) if w.strip()]

        # 금지어 체크
        for bad in forbidden:
            if not bad:
                continue
            if bad in suggestion:
                replacement = preferred or term or ""
                if replacement:
                    suggestion = suggestion.replace(bad, replacement)
                    issues.append(
                        {
                            "message": f"금지어 '{bad}' → '{replacement}' 교정",
                            "from": bad,
                            "to": replacement,
                            "kind": "forbidden",
                        }
                    )
                else:
                    issues.append(
                        {
                            "message": f"금지어 '{bad}' 제거",
                            "from": bad,
                            "to": "",
                            "kind": "forbidden",
                        }
                    )

        # 권장 용어 치환
        if preferred and preferred not in suggestion:
            for alias in aliases + [term]:
                if alias and re.search(rf"\b{re.escape(alias)}\b", suggestion):
                    suggestion = re.sub(
                        rf"\b{re.escape(alias)}\b", preferred, suggestion
                    )
                    issues.append(
                        {
                            "message": f"'{alias}' 대신 '{preferred}' 권장",
                            "from": alias,
                            "to": preferred,
                            "kind": "preferred",
                        }
                    )
                    break

    return {"issues": issues, "suggestion": suggestion, "hits": hits}


async def suggestion_by_project(db, project_id: str):
    # 1) 프로젝트의 세그먼트 찾기
    try:
        project_oid = ObjectId(project_id)
    except InvalidId:
        project_oid = project_id  # 이미 문자열로 저장된 경우 그대로 사용

    cursor = db["segments"].find({"project_id": project_oid})
    async for segment in cursor:
        await glosary_suggestion(db, segment["_id"])


async def glosary_suggestion(db: DbDep, segment_oid: str):
    segment = await db["segments"].find_one({"_id": segment_oid})
    source_text = (segment.get("segment_text") or "").strip()
    translated_text = (segment.get("translate_text") or "").strip()

    if not source_text or not translated_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Segment missing source or translated text",
        )

    # review = detect_glossary_issues(
    #     source=source_text,
    #     mt=translated_text,
    # )

    review = await rag_glossary_correction(
        source_text=source_text, draft_translation=translated_text
    )

    print(review)

    review["checked_at"] = datetime.now().isoformat() + "Z"

    for issue in review.get("issues", []):
        await db["issues"].insert_one(
            {
                "segment_id": segment_oid,
                "message": issue["message"],
                "from": issue["from"],
                "to": issue["to"],
                "created_at": datetime.now(),
            }
        )

    return review
