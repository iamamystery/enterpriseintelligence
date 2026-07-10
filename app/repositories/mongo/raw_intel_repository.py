from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase


class RawIntelRepository:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["raw_intel"]

    async def insert_raw(self, source: str, payload: dict[str, Any]) -> str:
        document = {
            "source": source,
            "payload": payload,
            "fetched_at": datetime.now(UTC),
        }
        result = await self.collection.insert_one(document)
        return str(result.inserted_id)
