from fastapi import APIRouter, Depends
from typing import List

from .service import ProjectService
from .models import ProjectTarget, ProjectTargetUpdate

target_router = APIRouter(prefix="/target", tags=["Project_Targets"])


@target_router.get("/{project_id}", summary="프로젝트 별 targets 조회")
async def get_targets_by_project(
    project_id: str,
    project_service: ProjectService = Depends(ProjectService),
) -> List[ProjectTarget]:
    targets = await project_service.get_targets_by_project(
        project_id=project_id,
    )
    return targets


@target_router.get(
    "/{project_id}/{language_code}",
    summary="프로젝트 및 언어 별 targets 조회",
)
async def get_targets_by_project_and_language(
    project_id: str,
    language_code: str,
    project_service: ProjectService = Depends(ProjectService),
) -> ProjectTarget:
    targets = await project_service.get_targets_by_project(
        project_id=project_id,
        language_code=language_code,
    )
    return targets[0]


@target_router.put("/{target_id}", summary="타겟 단일 수정")
async def update_targets_by_project(
    target_id: str,
    target: ProjectTargetUpdate,
    project_service: ProjectService = Depends(ProjectService),
) -> ProjectTarget:
    updated_targets = await project_service.update_targets(target_id, target)
    return updated_targets
