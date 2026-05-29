import re
from datetime import date, time, timedelta

from pydantic import BaseModel, field_validator
from typing import Optional

from config import IST
from datetime import datetime

PHONE_RE = re.compile(r"^\d{10}$")


class AppointmentCreate(BaseModel):
    customer_phone: str
    customer_name: str
    service_id: str
    staff_id: str
    appointment_date: date
    appointment_time: time

    @field_validator("customer_phone")
    @classmethod
    def validate_phone(cls, v):
        if not PHONE_RE.match(v):
            raise ValueError("Phone must be 10 digits")
        return v

    @field_validator("customer_name")
    @classmethod
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError("Customer name must be at least 2 characters")
        return v.strip()

    @field_validator("appointment_date")
    @classmethod
    def validate_date(cls, v):
        today = datetime.now(IST).date()
        if v < today:
            raise ValueError("Cannot book in the past")
        if v > today + timedelta(days=30):
            raise ValueError("Cannot book more than 30 days in advance")
        return v


class AppointmentResponse(BaseModel):
    id: str
    salon_id: str
    customer_id: str
    service_id: str
    staff_id: str
    appointment_date: date
    appointment_time: time
    status: str


class RescheduleRequest(BaseModel):
    new_date: date
    new_time: time

    @field_validator("new_date")
    @classmethod
    def validate_date(cls, v):
        today = datetime.now(IST).date()
        if v < today:
            raise ValueError("Cannot reschedule into the past")
        if v > today + timedelta(days=30):
            raise ValueError("Cannot reschedule more than 30 days in advance")
        return v
