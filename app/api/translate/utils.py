from dataclasses import dataclass
from typing import Any, List


@dataclass
class RetrievedDoc:
    kind: str
    text: str
    raw: dict[str, Any]
    score: float


def vector_search(query: str, top_k: int = 5) -> List[RetrievedDoc]:
    """Glossary vector search disabled."""
    return []
