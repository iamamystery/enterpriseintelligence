import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdvisoryCreate(BaseModel):
    advisory_id: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1)
    url: str | None = Field(default=None, max_length=1024)
    published_date: datetime | None = None
    cve_ids: list[str] = Field(default_factory=list)
    source_id: uuid.UUID


class AdvisoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    advisory_id: str
    title: str
    summary: str
    url: str | None
    published_date: datetime | None
    cve_ids: list[str]
    source_id: uuid.UUID
    created_at: datetime
