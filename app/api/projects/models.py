from pydantic import BaseModel


class ProjectCreate(BaseModel):
    filename: str


class ProjectUpdate(BaseModel):
    project_id: str
    status: str
    s3_key: str | None = None
