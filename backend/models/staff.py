import re

from pydantic import BaseModel, field_validator
from typing import Optional

PHONE_RE = re.compile(r"^\d{10}$")


class StaffCreate(BaseModel):
    staff_name: str
    phone: Optional[str] = None

    @field_validator("staff_name")
    @classmethod
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError("Staff name must be at least 2 characters")
        return v.strip()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v and not PHONE_RE.match(v):
            raise ValueError("Phone must be 10 digits")
        return v


class StaffResponse(BaseModel):
    id: str
    staff_name: str
    phone: Optional[str] = None
    salon_id: str
    is_active: bool
