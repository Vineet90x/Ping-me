from datetime import time

from pydantic import BaseModel, field_validator
from typing import Optional


class SettingsUpdate(BaseModel):
    opening_time: Optional[time] = None
    closing_time: Optional[time] = None
    days_advance_booking: Optional[int] = None
    min_advance_booking_minutes: Optional[int] = None
    max_concurrent: Optional[int] = None  # chairs / simultaneous appointments

    @field_validator("days_advance_booking")
    @classmethod
    def validate_days(cls, v):
        if v is not None and (v < 1 or v > 365):
            raise ValueError("Days must be between 1 and 365")
        return v

    @field_validator("min_advance_booking_minutes")
    @classmethod
    def validate_minutes(cls, v):
        if v is not None and (v < 0 or v > 1440):
            raise ValueError("Minutes must be between 0 and 1440")
        return v

    @field_validator("max_concurrent")
    @classmethod
    def validate_max_concurrent(cls, v):
        if v is not None and (v < 1 or v > 50):
            raise ValueError("Chairs (max_concurrent) must be between 1 and 50")
        return v


class SettingsResponse(BaseModel):
    salon_id: str
    opening_time: str
    closing_time: str
    days_advance_booking: int
    min_advance_booking_minutes: int
    max_concurrent: Optional[int] = None
