from typing import Set, List
import json
import time
from typing import Any
from collections import OrderedDict

from app.core.logging import logger


class StateStore:
    async def get(self, key: str) -> str | None:
        raise NotImplementedError

    async def set(self, key: str, value: str, ex: int | None = None):
        raise NotImplementedError

    async def delete(self, key: str):
        raise NotImplementedError

    async def exists(self, key: str) -> bool:
        raise NotImplementedError

    async def hget(self, name: str, key: str) -> str | None:
        raise NotImplementedError

    async def hset(self, name: str, key: str, value: str):
        raise NotImplementedError

    async def hdel(self, name: str, key: str):
        raise NotImplementedError

    async def hkeys(self, name: str) -> List[str]:
        raise NotImplementedError

    async def smembers(self, name: str) -> Set[str]:
        raise NotImplementedError

    async def sadd(self, name: str, member: str):
        raise NotImplementedError

    async def srem(self, name: str, member: str):
        raise NotImplementedError

    async def sismember(self, name: str, member: str) -> bool:
        raise NotImplementedError

    async def ping(self) -> bool:
        raise NotImplementedError


class RedisStateStore(StateStore):
    def __init__(self, redis_client):
        self._r = redis_client

    async def get(self, key: str) -> str | None:
        return await self._r.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        await self._r.set(key, value, ex=ex)

    async def delete(self, key: str):
        await self._r.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._r.exists(key))

    async def hget(self, name: str, key: str) -> str | None:
        return await self._r.hget(name, key)

    async def hset(self, name: str, key: str, value: str):
        await self._r.hset(name, key, value)

    async def hdel(self, name: str, key: str):
        await self._r.hdel(name, key)

    async def hkeys(self, name: str) -> List[str]:
        return await self._r.hkeys(name)

    async def smembers(self, name: str) -> Set[str]:
        return await self._r.smembers(name)

    async def sadd(self, name: str, member: str):
        await self._r.sadd(name, member)

    async def srem(self, name: str, member: str):
        await self._r.srem(name, member)

    async def sismember(self, name: str, member: str) -> bool:
        return bool(await self._r.sismember(name, member))

    async def ping(self) -> bool:
        try:
            return await self._r.ping()
        except Exception:
            return False


class LocalStateStore(StateStore):
    def __init__(self):
        self._data: dict[str, str] = {}
        self._hash_data: dict[str, dict[str, str]] = {}
        self._set_data: dict[str, Set[str]] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self._data[key] = value

    async def delete(self, key: str):
        self._data.pop(key, None)
        self._hash_data.pop(key, None)
        self._set_data.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._data or key in self._hash_data or key in self._set_data

    async def hget(self, name: str, key: str) -> str | None:
        store = self._hash_data.get(name)
        if store is None:
            return None
        return store.get(key)

    async def hset(self, name: str, key: str, value: str):
        if name not in self._hash_data:
            self._hash_data[name] = {}
        self._hash_data[name][key] = value

    async def hdel(self, name: str, key: str):
        store = self._hash_data.get(name)
        if store:
            store.pop(key, None)

    async def hkeys(self, name: str) -> List[str]:
        store = self._hash_data.get(name)
        return list(store.keys()) if store else []

    async def smembers(self, name: str) -> Set[str]:
        return set(self._set_data.get(name, set()))

    async def sadd(self, name: str, member: str):
        if name not in self._set_data:
            self._set_data[name] = set()
        self._set_data[name].add(member)

    async def srem(self, name: str, member: str):
        store = self._set_data.get(name)
        if store:
            store.discard(member)

    async def sismember(self, name: str, member: str) -> bool:
        store = self._set_data.get(name)
        if store is None:
            return False
        return member in store

    async def ping(self) -> bool:
        return True


class LRUCache:
    def __init__(self, maxsize: int = 10000, ttl: int = 3600):
        self._maxsize = maxsize
        self._ttl = ttl
        self._cache: OrderedDict[str, tuple[float, str]] = OrderedDict()

    async def get(self, key: str) -> str | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.time() < expires_at:
            self._cache.move_to_end(key)
            return value
        del self._cache[key]
        return None

    async def set(self, key: str, value: str, ttl: int | None = None):
        if len(self._cache) >= self._maxsize:
            self._cache.popitem(last=False)
        self._cache[key] = (time.time() + (ttl or self._ttl), value)

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    async def size(self) -> int:
        return len(self._cache)

    async def clear(self) -> int:
        count = len(self._cache)
        self._cache.clear()
        return count


_store_instance: StateStore | None = None


async def get_state_store() -> StateStore:
    global _store_instance
    if _store_instance is not None:
        return _store_instance

    from app.config import settings

    if settings.REDIS_URL:
        try:
            from app.redis import get_redis
            r = await get_redis()
            if r is not None:
                _store_instance = RedisStateStore(r)
                return _store_instance
        except Exception as e:
            logger.warning("redis_unavailable_falling_back_to_local_store", error=str(e))

    _store_instance = LocalStateStore()
    logger.info("using_local_state_store")
    return _store_instance


async def close_state_store():
    global _store_instance
    _store_instance = None
