from __future__ import annotations

import argparse
import asyncio
import json
import os
from functools import lru_cache
from typing import Any, List, Sequence

import google.auth
import httpx
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from .utils import vector_search, RetrievedDoc

load_dotenv()

GEMINI_MODEL_DEFAULT = "gemini-2.5-flash"
GEMINI_MODEL_ENV = "GEMINI_MODEL"
GEMINI_PROJECT_ENV = "GCP_PROJECT"
GEMINI_LOCATION_ENV = "GCP_LOCATION"
GEMINI_LOCATION_DEFAULT = "us-central1"


def _format_glossary(doc: RetrievedDoc) -> str:
    raw = doc.raw
    forbidden = ", ".join(raw.get("forbidden", [])) or "없음"
    aliases = ", ".join(raw.get("aliases", [])) or "없음"
    examples = "; ".join(raw.get("examples", [])) or "없음"
    domain = raw.get("domain", "일반")
    notes = raw.get("notes") or "없음"
    return (
        f"[용어] {raw.get('term', '미상')} (score={doc.score:.3f})\n"
        f" - 권장 번역: {raw.get('preferred', '')}\n"
        f" - 금지 번역: {forbidden}\n"
        f" - 대체어: {aliases}\n"
        f" - 예시: {examples}\n"
        f" - 도메인: {domain}\n"
        f" - 메모: {notes}"
    )


class RAGCorrector:
    SYSTEM_PROMPT = """You are a professional localization editor.

Goal:
- Detect the source language and translate into the opposite language (ENG ↔︎ KOR) in a natural, conversational tone.
- Enforce the glossary strictly: replace forbidden terms, apply preferred terms.
- Apply any additional refinements needed for fluency, tone, and clarity.

Output ONLY JSON:
{
  "corrected_text": "<최종 교정 문장 전체>",
  "message": "<LLM 교정 결과 메시지>",
  "notes": "<추가 메모, 필요 없으면 빈 문자열 또는 생략>"
}

Guidelines:
- `corrected_text`는 모든 수정을 반영한 최종본이어야 한다.
- `message`는 교정한 결과 기반의 수정 이유와 변경사항을 명사형으로 짧게 작성한다.
- 응답은 반드시 유효한 JSON이어야 한다."""

    def build_glossary_context(
        self, source_text: str, draft_translation: str, top_glossary: int
    ) -> str:
        query = f"{source_text.strip()}\n\n{draft_translation.strip()}"
        hits = vector_search(query, top_glossary)
        blocks = [_format_glossary(doc) for doc in hits]
        return "\n\n".join(blocks) if blocks else "자료 없음"

    async def correct(
        self,
        source_text: str,
        draft_translation: str,
        *,
        model: str | None = None,
        temperature: float = 0.1,
        top_glossary: int = 5,
    ) -> dict[str, Any]:
        context = self.build_glossary_context(
            source_text, draft_translation, top_glossary
        )
        user_prompt = (
            "[SOURCE]\n"
            f"{source_text.strip()}\n\n"
            "[DRAFT]\n"
            f"{draft_translation.strip()}\n\n"
            "[GLOSSARY]\n"
            f"{context}"
        )

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        response = await call_gemini(
            messages,
            model=model or os.getenv(GEMINI_MODEL_ENV, GEMINI_MODEL_DEFAULT),
            temperature=temperature,
        )

        corrected_text = response.get("corrected_text", draft_translation)
        message = response.get("message", "")
        notes = response.get("notes", "")

        issues = response.get("issues", [])
        if not isinstance(issues, list):
            issues = [issues]

        normalized_issues: list[dict[str, Any]] = []
        for issue in issues:
            if isinstance(issue, dict):
                normalized_issues.append(
                    {
                        "message": issue.get("message", ""),
                        "from": issue.get("from", ""),
                        "to": issue.get("to", ""),
                        "kind": issue.get("kind", "gemini"),
                    }
                )
            else:
                normalized_issues.append(
                    {
                        "message": str(issue),
                        "from": "",
                        "to": "",
                        "kind": "gemini",
                    }
                )

        return {
            "corrected_text": corrected_text,
            "context": context,
            "issues": normalized_issues,
            "message": message,
            "notes": notes,
        }


async def call_gemini(
    messages: Sequence[dict[str, Any]],
    *,
    model: str,
    temperature: float,
) -> dict[str, Any]:
    project = os.getenv(GEMINI_PROJECT_ENV)
    if not project:
        raise EnvironmentError("GCP_PROJECT must be set for Gemini calls.")
    location = os.getenv(GEMINI_LOCATION_ENV, GEMINI_LOCATION_DEFAULT)
    model_name = model or GEMINI_MODEL_DEFAULT

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    req = Request()
    loop = asyncio.get_running_loop()

    def _refresh() -> None:
        credentials.refresh(req)

    await loop.run_in_executor(None, _refresh)
    if not credentials.token:
        raise RuntimeError("Failed to obtain access token for Gemini call.")

    system_parts: List[dict[str, str]] = []
    contents: List[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        if role == "system":
            system_parts.append({"text": content})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": content}]})
        else:
            contents.append({"role": "user", "parts": [{"text": content}]})

    if not contents:
        raise ValueError("Gemini call requires at least one non-system message.")

    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "responseMimeType": "application/json",
        },
    }
    if temperature:
        payload["generationConfig"]["temperature"] = float(temperature)
    if system_parts:
        payload["systemInstruction"] = {"role": "system", "parts": system_parts}

    endpoint = (
        f"https://{location}-aiplatform.googleapis.com/v1/projects/"
        f"{project}/locations/{location}/publishers/google/models/"
        f"{model_name}:generateContent"
    )
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(endpoint, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError(f"Gemini returned no candidates: {data}")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise ValueError(f"Gemini response missing parts: {data}")
    text = parts[0].get("text", "")
    json_text = _extract_json_block(text)
    return json.loads(json_text)


def _extract_json_block(text: str) -> str:
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in completion: {text!r}")
    depth = 0
    for idx in range(start, len(text)):
        ch = text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    raise ValueError(f"Incomplete JSON object in completion: {text!r}")


async def correct_with_rag(
    source_text: str,
    draft_translation: str,
    *,
    model: str | None = None,
    temperature: float = 0.1,
    top_glossary: int = 5,
) -> dict[str, Any]:
    corrector = _get_corrector()
    return await corrector.correct(
        source_text,
        draft_translation,
        model=model,
        temperature=temperature,
        top_glossary=top_glossary,
    )


async def rag_glossary_correction(
    source_text: str,
    draft_translation: str,
    *,
    temperature: float = 0.1,
    top_glossary: int = 5,
) -> dict[str, Any]:
    return await correct_with_rag(
        source_text,
        draft_translation,
        model=os.getenv(GEMINI_MODEL_ENV, GEMINI_MODEL_DEFAULT),
        temperature=temperature,
        top_glossary=top_glossary,
    )


@lru_cache(maxsize=1)
def _get_corrector() -> RAGCorrector:
    return RAGCorrector()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Gemini-based glossary correction."
    )
    parser.add_argument("--source", required=True, help="원문 텍스트")
    parser.add_argument("--draft", required=True, help="초안 번역")
    parser.add_argument(
        "--model", default=os.getenv(GEMINI_MODEL_ENV, GEMINI_MODEL_DEFAULT)
    )
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--top-glossary", type=int, default=5)
    return parser.parse_args(argv)
