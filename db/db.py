import os
from datetime import datetime
from typing import List, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection

from utils.config import Settings


class MongoDB:
    _instance = None
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    urls: Optional[AsyncIOMotorCollection] = None
    states: Optional[AsyncIOMotorCollection] = None

    URLS_COLLECTION = os.getenv("MONGODB_MONITOR_URLS_COLLECTION")
    TIMESTAMPS_COLLECTION = os.getenv("MONGODB_TIMESTAMPS_COLLECTION")

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDB, cls).__new__(cls)
        return cls._instance

    @classmethod
    async def connect(cls, settings: Settings):
        if not cls.client:
            cls.client = AsyncIOMotorClient(settings.MONGODB_URI)
            cls.db = cls.client[settings.MONGODB_DB]
            cls.urls = cls.db[cls.URLS_COLLECTION]
            cls.states = cls.db[cls.TIMESTAMPS_COLLECTION]
            await cls.create_indexes()

    @classmethod
    async def create_indexes(cls):
        await cls.urls.create_index("url", unique=True)
        await cls.states.create_index("monitor_type", unique=True)

    @classmethod
    async def close(cls):
        if cls.client:
            cls.client.close()
            cls.client = None
            cls.db = None
            cls.urls = None
            cls.states = None

    @classmethod
    async def get_urls(cls) -> List[Dict]:
        return await cls.urls.find().to_list(length=None)

    @classmethod
    async def add_url(cls, url: str, name: str):
        await cls.urls.update_one(
            {"url": url},
            {
                "$set": {
                    "name": name,
                    "updated_at": datetime.now()
                },
                "$setOnInsert": {"created_at": datetime.now()}
            },
            upsert=True
        )

    @classmethod
    async def remove_url(cls, url: str):
        await cls.urls.delete_one({"url": url})

    @classmethod
    async def get_last_check_time(cls, monitor_type: str) -> datetime:
        state = await cls.states.find_one({"monitor_type": monitor_type})
        return datetime.fromisoformat(state["last_check"]) if state else datetime.now()

    @classmethod
    async def update_last_check_time(cls, monitor_type: str, check_time: datetime):
        await cls.states.update_one(
            {"monitor_type": monitor_type},
            {
                "$set": {
                    "last_check": check_time.isoformat(),
                    "updated_at": datetime.now()
                }
            },
            upsert=True
        )
