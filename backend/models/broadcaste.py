from pydantic import BaseModel, field_validator
from typing import Optional


class BroadcastCreate(BaseModel):
    message_text: str
    image_url: Optional[str] = None

    @field_validator("message_text")
    @classmethod
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Message must be at least 5 characters")
        if len(v) > 500:
            raise ValueError("Message max 500 characters")
        return v

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, v):
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Invalid image URL")
        return v


class BroadcastResponse(BaseModel):
    id: str
    salon_id: str
    message_text: str
    image_url: Optional[str] = None
    sent_count: int
    created_at: Optional[str] = None
