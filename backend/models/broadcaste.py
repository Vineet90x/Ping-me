from pydantic import BaseModel, field_validator
from typing import Optional


class BroadcastCreate(BaseModel):
    message_text: str
    image_url: Optional[str] = None
    # When `headline` is set, the server generates a banner image (and ignores
    # any image_url). `subtext` is an optional second line on the banner.
    headline: Optional[str] = None
    subtext: Optional[str] = None

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

    @field_validator("headline")
    @classmethod
    def validate_headline(cls, v):
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 80:
            raise ValueError("Headline max 80 characters")
        return v

    @field_validator("subtext")
    @classmethod
    def validate_subtext(cls, v):
        if v is None:
            return None
        v = v.strip()
        if len(v) > 120:
            raise ValueError("Subtext max 120 characters")
        return v or None


class BroadcastResponse(BaseModel):
    id: str
    salon_id: str
    message_text: str
    image_url: Optional[str] = None
    sent_count: int
    created_at: Optional[str] = None
