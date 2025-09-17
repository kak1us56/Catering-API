import os
import json
from dataclasses import dataclass

import redis

@dataclass
class Sctucture:
    id: int
    name: str

class CacheService:
    def __init__(self):
        self.connection: redis.Redis = redis.Redis.from_url(os.getenv("DJANGO_CACHE_URL", default="redis://localhost:6379/0"))
        # self.connection: redis.Redis = redis.Redis.from_url("redis://localhost:6379/0")

    @staticmethod
    def _build_key(namespace: str, key: str) -> str:
        return f"{namespace}:{key}"

    def get_ttl(self, namespace: str, key: str) -> int:
        key = self._build_key(namespace, key)

        return self.connection.ttl(key)

    def set(self, namespace: str, key: str, value: dict, ttl: int | None = None):
        key = self._build_key(namespace, key)

        self.connection.set(key, value=json.dumps(value), ex=ttl)

    def get(self, namespace: str, key: str):
        result: str = self.connection.get(self._build_key(namespace, key))

        return json.loads(result)

    def delete(self, namespace: str, key: str):
        self.connection.delete(self._build_key(namespace, key))
