from pydantic import BaseModel


class PresignRequest(BaseModel):
    filename: str
    content_type: str
