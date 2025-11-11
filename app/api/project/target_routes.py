from fastapi import APIRouter, Depends
from typing import List

from .service import ProjectService
from .models import ProjectTarget

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
