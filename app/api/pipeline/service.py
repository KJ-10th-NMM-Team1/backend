from fastapi import HTTPException, status
from datetime import datetime
from pymongo.errors import PyMongoError
from typing import TypedDict, Dict, Any
from bson import ObjectId
from bson.errors import InvalidId

from ..deps import DbDep
from .models import PipelineUpdate, ProjectPipeline, PipelineStage, PipelineStatus


class PipelineUpdateResult(TypedDict):
    success: bool


async def get_pipeline_status(db: DbDep, project_id: str) -> ProjectPipeline:
    """프로젝트의 파이프라인 상태 조회"""
    try:
        # 프로젝트 존재 확인
        project = await db["projects"].find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # 파이프라인 상태 조회 (없으면 기본값 생성)
        pipeline_doc = await db["pipelines"].find_one({"project_id": project_id})
        
        if not pipeline_doc:
            # 기본 파이프라인 생성
            pipeline_doc = await _create_default_pipeline(db, project_id)
        
        return _doc_to_pipeline(pipeline_doc)
        
    except InvalidId as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project_id"
        ) from exc
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pipeline status"
        ) from exc


async def update_pipeline_stage(db: DbDep, payload: PipelineUpdate) -> PipelineUpdateResult:
    """파이프라인 단계 상태 업데이트"""
    try:
        project_id = payload.project_id
        stage_id = payload.stage_id
        
        # 파이프라인 문서 조회
        pipeline_doc = await db["pipelines"].find_one({"project_id": project_id})
        if not pipeline_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found"
            )
        
        # 해당 단계 찾기 및 업데이트
        stages = pipeline_doc["stages"]
        stage_found = False
        
        for stage in stages:
            if stage["id"] == stage_id:
                stage["status"] = payload.status.value
                if payload.progress is not None:
                    stage["progress"] = payload.progress
                if payload.error:
                    stage["error"] = payload.error
                
                # 상태에 따른 타임스탬프 업데이트
                now = datetime.now()
                if payload.status == PipelineStatus.PROCESSING:
                    stage["started_at"] = now
                elif payload.status in [PipelineStatus.COMPLETED, PipelineStatus.FAILED]:
                    stage["completed_at"] = now
                
                stage_found = True
                break
        
        if not stage_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stage not found"
            )
        
        # 전체 진행률 계산
        completed_stages = sum(1 for stage in stages if stage["status"] == "completed")
        overall_progress = int((completed_stages / len(stages)) * 100)
        
        # 현재 단계 업데이트
        current_stage = _get_current_stage(stages)
        
        # 데이터베이스 업데이트
        await db["pipelines"].update_one(
            {"project_id": project_id},
            {
                "$set": {
                    "stages": stages,
                    "current_stage": current_stage,
                    "overall_progress": overall_progress,
                    "updated_at": now
                }
            }
        )
        
        return {"success": True}
        
    except PyMongoError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update pipeline stage"
        ) from exc


async def _create_default_pipeline(db: DbDep, project_id: str) -> Dict[str, Any]:
    """기본 파이프라인 생성"""
    now = datetime.now()
    
    default_stages = [
        {"id": "upload", "status": "completed", "progress": 100, "started_at": now, "completed_at": now},
        {"id": "stt", "status": "processing", "progress": 45, "started_at": now},
        {"id": "mt", "status": "pending", "progress": 0},
        {"id": "rag", "status": "pending", "progress": 0},
        {"id": "tts", "status": "pending", "progress": 0},
        {"id": "packaging", "status": "pending", "progress": 0},
        {"id": "outputs", "status": "pending", "progress": 0}
    ]
    
    pipeline_doc = {
        "project_id": project_id,
        "stages": default_stages,
        "current_stage": "stt",
        "overall_progress": 14,  # 1/7 완료
        "created_at": now,
        "updated_at": now
    }
    
    result = await db["pipelines"].insert_one(pipeline_doc)
    pipeline_doc["_id"] = result.inserted_id
    
    return pipeline_doc


def _doc_to_pipeline(doc: Dict[str, Any]) -> ProjectPipeline:
    """MongoDB 문서를 ProjectPipeline 모델로 변환"""
    stages = []
    for stage_doc in doc["stages"]:
        stage = PipelineStage(
            id=stage_doc["id"],
            status=PipelineStatus(stage_doc["status"]),
            progress=stage_doc["progress"],
            started_at=stage_doc.get("started_at"),
            completed_at=stage_doc.get("completed_at"),
            error=stage_doc.get("error")
        )
        stages.append(stage)
    
    return ProjectPipeline(
        project_id=doc["project_id"],
        stages=stages,
        current_stage=doc["current_stage"],
        overall_progress=doc["overall_progress"]
    )


def _get_current_stage(stages: list) -> str:
    """현재 진행 중인 단계 찾기"""
    for stage in stages:
        if stage["status"] in ["processing", "review"]:
            return stage["id"]
    
    # 진행 중인 단계가 없으면 첫 번째 pending 단계
    for stage in stages:
        if stage["status"] == "pending":
            return stage["id"]
    
    # 모든 단계가 완료되었으면 마지막 단계
    return stages[-1]["id"] if stages else ""