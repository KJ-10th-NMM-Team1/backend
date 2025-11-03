import json
import os
import re
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List
from fastapi import HTTPException, status
import faiss
from sentence_transformers import SentenceTransformer

from ..deps import DbDep

STORE_DIR = Path(os.getenv("GLOSSARY_STORE_DIR", "store"))
GLOSSARY_INDEX_PATH = STORE_DIR / "glossary.faiss"
GLOSSARY_META_PATH = STORE_DIR / "glossary.jsonl"

MODEL_NAME = os.getenv("GLOSSARY_EMBED_MODEL", "BAAI/bge-m3")

_DOCS: list[dict[str, Any]] | None = None
_INDEX: faiss.Index | None = None
_MODEL: SentenceTransformer | None = None


@dataclass
class RetrievedDoc:
    kind: str
    text: str
    raw: dict[str, Any]
    score: float


def vector_search(query: str, top_k: int = 5):
    global _INDEX, _DOCS, _MODEL

    if not query.strip():
        return []
    normalized = (query or "").strip()
    if not normalized:
        return []

    #  전역으로 필요할때 한번만 로드
    if _DOCS is None:
        if not GLOSSARY_META_PATH.exists():
            return []
        with open(GLOSSARY_META_PATH, "r", encoding="utf-8") as f:
            _DOCS = [json.loads(line) for line in f]

    if _INDEX is None:
        if not GLOSSARY_INDEX_PATH.exists():
            return []
        _INDEX = faiss.read_index(str(GLOSSARY_INDEX_PATH))

    if _MODEL is None:
        _MODEL = SentenceTransformer(MODEL_NAME)

    if query == "warmup":
        return

    query_emb = _MODEL.encode(
        [normalized],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    scores, indices = _INDEX.search(query_emb.astype("float32"), top_k)

    results: List[RetrievedDoc] = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(_DOCS):
            continue
        doc = _DOCS[idx]
        results.append(
            RetrievedDoc(
                kind=doc.get("kind", "glossary"),
                text=doc.get("text", ""),
                raw=doc.get("raw", {}),
                score=float(score),
            )
        )

    return results


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


async def glosary_suggestion(db: DbDep, segment_oid: str):
    segment = await db["segments"].find_one({"_id": segment_oid})
    source_text = (segment.get("segment_text") or "").strip()
    translated_text = (segment.get("translate_text") or "").strip()

    if not source_text or not translated_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Segment missing source or translated text",
        )

    review = detect_glossary_issues(
        source=source_text,
        mt=translated_text,
    )
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
