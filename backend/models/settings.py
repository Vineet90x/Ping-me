from pydantic import BaseModel, validator
from datetime import time

class SettingsUpdate(BaseModel):
    opening_time: time = None
    closing_time: time = None
    days_advance_booking: int = None
    min_advance_booking_minutes: int = None
    
    @validator('days_advance_booking')
    def validate_days(cls, v):
        if v and (v < 1 or v > 365):
            raise ValueError('Days must be between 1 and 365')
        return v
    
    @validator('min_advance_booking_minutes')
    def validate_minutes(cls, v):
        if v and (v < 0 or v > 1440):
            raise ValueError('Minutes must be between 0 and 1440')
        return v

class SettingsResponse(BaseModel):
    salon_id: str
    opening_time: str
    closing_time: str
    days_advance_booking: int
    min_advance_booking_minutes: int