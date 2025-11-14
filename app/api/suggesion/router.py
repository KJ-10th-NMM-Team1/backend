from fastapi import APIRouter, Depends, status, Response, HTTPException
from .service import Model
from .models import SuggestionResponse, SuggestionRequest, SuggestSave, SuggestDelete
from .status import EnumStatus

"""
@author: 김현수
"""
suggestion_router = APIRouter(prefix="/suggestion", tags=["AI Sugession"])

@suggestion_router.get("/{segment_id}", response_model=str, status_code=status.HTTP_200_OK)
async def model_sugession(segment_id: str, request_context: str, sugession_service: Model = Depends(Model)):
    try:
        req_context = EnumStatus(int(request_context)).label()
    except (ValueError, KeyError):
        raise HTTPException(status_code=400, detail="잘못된 request_context 값입니다.")

    result = await sugession_service.prompt_text(segment_id, req_context)
    if not result:
        raise HTTPException(status_code=500, detail="AI 모델 응답 생성 실패")
    return result

@suggestion_router.get("/list", response_model=str, status_code=status.HTTP_200_OK)
async def model_sugession(sugession_service: Model = Depends(Model)):
    result = await sugession_service.get_suggestion_list()
    return result

@suggestion_router.get("/detail/{segment_id}", response_model=SuggestionResponse, status_code=status.HTTP_200_OK)
async def get_suggestion(
    suggestion_id: str,
    service: Model = Depends(Model)
):
    doc = await service.get_suggestion_by_id(suggestion_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found"
        )
    return doc

@suggestion_router.delete("/{segment_id}", response_model=str, status_code=status.HTTP_200_OK)
async def model_sugession_delete(request: SuggestDelete, sugession_service: Model = Depends(Model)):
    result = await sugession_service.delete_suggession_by_id(request.segment_id)
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found"
        )
    return Response(status_code=status.HTTP_200_OK)

@suggestion_router.put("/{segment_id}", response_model=SuggestionResponse, status_code=status.HTTP_201_CREATED)
async def model_sugession_save(request: SuggestSave, sugession_service: Model = Depends(Model)):
    inserted_id = await sugession_service.save_prompt_text(request.segment_id)
    if not inserted_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found"
        )
    return await sugession_service.get_suggession_by_id(inserted_id)

@suggestion_router.post("/{segment_id}", response_model=SuggestionResponse, status_code=status.HTTP_200_OK)
async def model_sugession_update(request: SuggestionRequest, sugession_service: Model = Depends(Model)):
    inserted_id = await sugession_service.update_suggession_by_id(request)
    if not inserted_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found"
        )
    return await sugession_service.get_suggession_by_id(inserted_id)

