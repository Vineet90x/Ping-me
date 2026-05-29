import redis
import json
import os
from datetime import datetime, timedelta

REDIS_URL = os.getenv("REDIS_URL")
r = redis.from_url(REDIS_URL)

class Session:
    def __init__(self, phone: str):
        self.phone = phone
        self.key = f"session:{phone}"
    
    def get(self):
        """Get session data"""
        data = r.get(self.key)
        return json.loads(data) if data else None
    
    def set(self, data: dict, ttl: int = 1800):
        """Set session data (30 min default)"""
        r.setex(self.key, ttl, json.dumps(data))
    
    def update(self, data: dict):
        """Update existing session"""
        current = self.get() or {}
        current.update(data)
        self.set(current)
    
    def delete(self):
        """Clear session"""
        r.delete(self.key)
    
    def exists(self):
        """Check if session exists"""
        return r.exists(self.key) > 0