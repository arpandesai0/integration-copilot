from datetime import datetime
from functools import lru_cache

from pymongo import ASCENDING, MongoClient

from app.config import settings


class MongoChatStore:
    def __init__(self, uri: str, database_name: str):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self.database = self.client[database_name]
        self.messages = self.database.chat_messages

    def initialize(self):
        self.client.admin.command("ping")
        self.messages.create_index("message_id", unique=True)
        self.messages.create_index(
            [("device_id", ASCENDING), ("thread_id", ASCENDING), ("created_at", ASCENDING)]
        )
        self.messages.create_index(
            [("device_id", ASCENDING), ("workspace_id", ASCENDING)]
        )

    def save(self, message, *, device_id: str, workspace_id: str):
        document = {
            "message_id": message.id,
            "device_id": device_id,
            "workspace_id": workspace_id,
            "thread_id": message.thread_id,
            "role": message.role,
            "content": message.content,
            "status": message.status,
            "citations": message.citations or [],
            "created_at": message.created_at,
            "updated_at": datetime.utcnow(),
        }
        self.messages.replace_one(
            {"message_id": message.id, "device_id": device_id},
            document,
            upsert=True,
        )

    def list(self, *, thread_id: str, device_id: str):
        records = self.messages.find(
            {"thread_id": thread_id, "device_id": device_id}, {"_id": 0}
        ).sort("created_at", ASCENDING)
        return [
            {
                "id": item["message_id"],
                "thread_id": item["thread_id"],
                "role": item["role"],
                "content": item["content"],
                "status": item["status"],
                "citations": item.get("citations", []),
                "created_at": item["created_at"],
            }
            for item in records
        ]

    def delete_workspace(self, *, workspace_id: str, device_id: str):
        self.messages.delete_many(
            {"workspace_id": workspace_id, "device_id": device_id}
        )


@lru_cache
def get_chat_store():
    if not settings.mongodb_uri:
        return None
    return MongoChatStore(settings.mongodb_uri, settings.mongodb_database)

