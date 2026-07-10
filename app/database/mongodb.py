from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

client: AsyncIOMotorClient = AsyncIOMotorClient(settings.MONGODB_URL)
database: AsyncIOMotorDatabase = client[settings.MONGODB_DB_NAME]


def get_mongodb() -> AsyncIOMotorDatabase:
    return database
