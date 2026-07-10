from typing import Generic, TypeVar

from pydantic import BaseModel

from app.schemas.advisory import AdvisoryRead
from app.schemas.asset import AssetRead
from app.schemas.vulnerability import VulnerabilityRead

T = TypeVar("T")


class SearchResultGroup(BaseModel, Generic[T]):
    items: list[T]
    total: int


class SearchResponse(BaseModel):
    query: str
    vulnerabilities: SearchResultGroup[VulnerabilityRead]
    advisories: SearchResultGroup[AdvisoryRead]
    assets: SearchResultGroup[AssetRead]
