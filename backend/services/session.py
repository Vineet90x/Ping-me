"""Conversation session store for the WhatsApp booking flow.

Uses Redis when ``REDIS_URL`` is configured, otherwise falls back to an
in-memory store so local testing works without Redis (single process only).
"""
import json
import logging
import time

from config import REDIS_URL

logger = logging.getLogger("ping.session")

_redis = None
if REDIS_URL:
    try:
        import redis

        _redis = redis.from_url(REDIS_URL, decode_responses=True)
        _redis.ping()
        logger.info("Session store: Redis")
    except Exception as exc:  # pragma: no cover - depends on infra
        logger.warning("Redis unavailable (%s); using in-memory sessions", exc)
        _redis = None

# In-memory fallback: phone -> (expires_at_epoch, json_string)
_memory: dict[str, tuple[float, str]] = {}


class Session:
    DEFAULT_TTL = 1800  # 30 minutes

    def __init__(self, phone: str):
        self.phone = phone
        self.key = f"session:{phone}"

    def get(self) -> dict | None:
        if _redis is not None:
            data = _redis.get(self.key)
            return json.loads(data) if data else None
        entry = _memory.get(self.key)
        if not entry:
            return None
        expires_at, data = entry
        if time.time() > expires_at:
            _memory.pop(self.key, None)
            return None
        return json.loads(data)

    def set(self, data: dict, ttl: int = DEFAULT_TTL) -> None:
        payload = json.dumps(data)
        if _redis is not None:
            _redis.setex(self.key, ttl, payload)
        else:
            _memory[self.key] = (time.time() + ttl, payload)

    def update(self, data: dict) -> None:
        current = self.get() or {}
        current.update(data)
        self.set(current)

    def delete(self) -> None:
        if _redis is not None:
            _redis.delete(self.key)
        else:
            _memory.pop(self.key, None)

    def exists(self) -> bool:
        return self.get() is not None
