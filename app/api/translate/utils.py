import json
import os
from pathlib import Path
import faiss
from typing import Any, List
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer

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
