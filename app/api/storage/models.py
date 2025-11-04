from pydantic import BaseModel


class PresignRequest(BaseModel):
    filename: str
    content_type: str
    owner_code: str


class UploadFinalize(BaseModel):
    project_id: str
    object_key: str


class UploadFail(BaseModel):
    project_id: str
