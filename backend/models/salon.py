import re

from pydantic import BaseModel, field_validator
from typing import Optional

PHONE_RE = re.compile(r"^\d{10}$")
UPI_RE = re.compile(r"^[a-zA-Z0-9.\-_]+@[a-zA-Z]{3,}$")


class SalonRegister(BaseModel):
    owner_phone: str
    owner_name: str
    salon_name: str
    upi_id: Optional[str] = None

    @field_validator("owner_phone")
    @classmethod
    def validate_phone(cls, v):
        if not PHONE_RE.match(v):
            raise ValueError("Phone must be 10 digits")
        return v

    @field_validator("owner_name", "salon_name")
    @classmethod
    def validate_names(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError("Must be at least 2 characters")
        return v.strip()

    @field_validator("upi_id")
    @classmethod
    def validate_upi(cls, v):
        if v and not UPI_RE.match(v):
            raise ValueError("Invalid UPI format (e.g., name@bank)")
        return v


class SalonUpdate(BaseModel):
    owner_name: Optional[str] = None
    salon_name: Optional[str] = None
    upi_id: Optional[str] = None

    @field_validator("owner_name", "salon_name")
    @classmethod
    def validate_names(cls, v):
        if v is None:
            return None
        if len(v.strip()) < 2:
            raise ValueError("Must be at least 2 characters")
        return v.strip()

    @field_validator("upi_id")
    @classmethod
    def validate_upi(cls, v):
        if v and not UPI_RE.match(v):
            raise ValueError("Invalid UPI format (e.g., name@bank)")
        return v


class SalonResponse(BaseModel):
    id: str
    owner_phone: str
    owner_name: str
    salon_name: str
    upi_id: Optional[str] = None
    plan_type: str
    api_key: Optional[str] = None  # returned on registration and /me; keep it safe
