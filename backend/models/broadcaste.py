from pydantic import BaseModel, validator
from typing import Optional

class BroadcastCreate(BaseModel):
    message_text: str
    image_url: Optional[str] = None
    
    @validator('message_text')
    def validate_message(cls, v):
        if not v or len(v.strip()) < 5:
            raise ValueError('Message must be at least 5 characters')
        if len(v.strip()) > 500:
            raise ValueError('Message max 500 characters')
        return v.strip()
    
    @validator('image_url')
    def validate_image_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('Invalid image URL')
        return v

class BroadcastResponse(BaseModel):
    id: str
    salon_id: str
    message_text: str
    image_url: Optional[str] = None
    sent_count: int
    created_at: str