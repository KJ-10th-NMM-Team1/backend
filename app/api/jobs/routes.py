from fastapi import APIRouter

from ..deps import DbDep
from .models import JobRead, JobUpdateStatus
from .service import get_job, update_job_status

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRead)
async def read_job(job_id: str, db: DbDep) -> JobRead:
    return await get_job(db, job_id)


@router.post("/{job_id}/status", response_model=JobRead)
async def set_job_status(job_id: str, payload: JobUpdateStatus, db: DbDep) -> JobRead:
    return await update_job_status(db, job_id, payload)
