import logging
from datetime import datetime
from bson import ObjectId

import vertexai
from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel

from app.config.env import (
    GEMINI_MODEL_VERSION,
    GOOGLE_APPLICATION_CREDENTIALS,
    VERTEX_LOCATION,
    VERTEX_PROJECT_ID,
)
from ..deps import DbDep
from .models import SuggestionRequest, SuggestionResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Model:
    def __init__(self, db: DbDep):
        self.suggesion_prompt_collection = db.get_collection("suggesion_prompt")
        self.project_segemnts_collection = db.get_collection("project_segments")
        self.segment_translations_collection = db.get_collection("segment_translations")
        self.languages_collection = db.get_collection("languages")

        sa_path = GOOGLE_APPLICATION_CREDENTIALS
        try:
            self.project_id = VERTEX_PROJECT_ID
            self.location = VERTEX_LOCATION
            self.model_name = GEMINI_MODEL_VERSION
            if not all([self.project_id, self.location, self.model_name, sa_path]):
                raise ValueError(
                    "필수 환경 변수(PROJECT_ID, LOCATION, MODEL, CREDENTIALS)가 설정되지 않았습니다."
                )

            credentials = service_account.Credentials.from_service_account_file(
                sa_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )

            vertexai.init(
                project=self.project_id,
                location=self.location,
                credentials=credentials,
            )
            self.model = GenerativeModel(self.model_name)
            logger.info(
                "Vertex AI 초기화 성공 (Project: %s, Model: %s)",
                self.project_id,
                self.model_name,
            )
        except Exception as exc:
            self.model = None
            logger.error("Vertex AI 초기화 오류: %s", exc)
            logger.error("사용된 JSON 경로: %s", sa_path)

    async def prompt_text(self, segment_id: str, request_context: str) -> str:
        if not self.model:
            logger.error("Gemini 모델이 초기화되지 않았습니다.")
            return ""

        project_segment = await self.project_segemnts_collection.find_one(
            {"_id": ObjectId(segment_id)}
        )
        trans_segment = await self.segment_translations_collection.find_one(
            {"segment_id": segment_id}
        )

        if not project_segment or not trans_segment:
            logger.error("세그먼트 정보를 찾을 수 없습니다: %s", segment_id)
            return ""

        language_code = trans_segment.get("language_code")
        languages_collection = await self.languages_collection.find_one(
            {"language_code": language_code}
        )
        language_name = languages_collection.get("name_ko") if languages_collection else ""

        prompt = f"""
        [역활]: 당신은 전문 더빙 대본 편집자입니다.
        [원문]: {project_segment.get('source_text', '')}
        [번역문]: {trans_segment.get('target_text', '')}
        [요청]: {request_context}
        [규칙]: 1. 여러 가지 제안이나 설명을 절대 하지 마세요.
               2. 수정된 최종 {language_name} 대본 하나만 응답으로 주세요.
               3. 수정된 대본 외에 어떤 텍스트도 추가하지 마세요.
               4. 응답의 앞이나 뒤에 따옴표("), 별표(*), 하이픈(-) 같은 서식용 문자를 절대 붙이지 마세요.
        """

        try:
            response = await self.model.generate_content_async(prompt)
        except Exception as exc:
            logger.error("Gemini API 호출 오류: %s", exc)
            return ""

        if not response:
            return ""
        return response.text.strip()

    async def save_prompt_text(self, segment_id: str) -> str:
        project_segment = await self.project_segemnts_collection.find_one(
            {"_id": ObjectId(segment_id)}
        )
        trans_segment = await self.segment_translations_collection.find_one(
            {"segment_id": segment_id}
        )
        if not project_segment or not trans_segment:
            raise ValueError("세그먼트 정보를 찾을 수 없습니다.")

        document_to_save = {
            "segment_id": segment_id,
            "original_text": project_segment.get("source_text", ""),
            "translate_text": trans_segment.get("target_text", ""),
            "sugession_text": None,
            "created_at": datetime.utcnow(),
        }

        result = await self.suggesion_prompt_collection.insert_one(document_to_save)
        return str(result.inserted_id)

    async def get_suggession_by_id(self, segment_id: str):
        doc = await self.suggesion_prompt_collection.find_one(
            {"$or": [{"_id": ObjectId(segment_id)}, {"segment_id": segment_id}]}
        )
        if doc:
            return SuggestionResponse(**doc)
        return None

    async def delete_suggession_by_id(self, segment_id: str):
        return await self.suggesion_prompt_collection.delete_one(
            {"segment_id": segment_id}
        )

    async def update_suggession_by_id(self, request: SuggestionRequest):
        update_data = request.model_dump(exclude_unset=True)

        await self.suggesion_prompt_collection.update_one(
            {"segment_id": request.segment_id},
            {"$set": update_data},
        )
        return str(request.segment_id)

    async def get_suggession_list(self):
        docs = await self.suggesion_prompt_collection.find({}).to_list(length=None)
        return [SuggestionResponse(**doc) for doc in docs]
