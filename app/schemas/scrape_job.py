import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScrapeJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_name: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    items_processed: int | None
    error_message: str | None
    created_at: datetime
