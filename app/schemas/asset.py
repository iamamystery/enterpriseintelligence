import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    asset_type: str = Field(min_length=1, max_length=50)
    vendor: str | None = Field(default=None, max_length=255)
    product: str | None = Field(default=None, max_length=255)
    version: str | None = Field(default=None, max_length=100)
    ip_address: str | None = Field(default=None, max_length=45)


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    asset_type: str
    vendor: str | None
    product: str | None
    version: str | None
    ip_address: str | None
    is_active: bool
    organization_id: uuid.UUID
    created_at: datetime
