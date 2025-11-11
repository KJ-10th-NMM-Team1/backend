from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status

from .models import AssetCreate, AssetOut
from .service import AssetService


assets_router = APIRouter(prefix="/assets", tags=["Assets"])


@assets_router.post(
    "/{project_id}",
    response_model=AssetOut,
    status_code=status.HTTP_201_CREATED,
    summary="프로젝트 산출물 등록",
)
async def create_asset(
    project_id: str,
    payload: AssetCreate,
    asset_service: AssetService = Depends(AssetService),
) -> AssetOut:
    payload_dict = payload.model_dump()
    payload_dict.update({"project_id": project_id})
    return await asset_service.create_asset(AssetCreate(**payload_dict))


@assets_router.get(
    "/{project_id}",
    response_model=List[AssetOut],
    summary="프로젝트 산출물 목록 조회",
)
async def list_assets(
    project_id: str,
    language_code: Optional[str] = Query(
        None, description="선택적으로 asset 언어 코드를 기준으로 필터링"
    ),
    type: Optional[str] = Query(
        None, description="선택적으로 asset 타입을 기준으로 필터링"
    ),
    asset_service: AssetService = Depends(AssetService),
) -> List[AssetOut]:
    return await asset_service.list_assets(project_id, language_code, type)


@assets_router.get(
    "/{asset_id}",
    response_model=AssetOut,
    summary="프로젝트 산출물 상세 조회",
)
async def get_asset(
    asset_id: str, asset_service: AssetService = Depends(AssetService)
) -> AssetOut:
    return await asset_service.get_asset(asset_id)
