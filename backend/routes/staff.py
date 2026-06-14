from typing import Optional
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from models.staff import StaffCreate, StaffResponse
from services.database import get_db

router = APIRouter()

PHONE_RE = re.compile(r"^\d{10}$")


class StaffUpdate(BaseModel):
    staff_name: Optional[str] = None
    phone: Optional[str] = None

    @field_validator("staff_name")
    @classmethod
    def validate_name(cls, v):
        if v is not None and len(v.strip()) < 2:
            raise ValueError("Staff name must be at least 2 characters")
        return v.strip() if v else v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v and not PHONE_RE.match(v):
            raise ValueError("Phone must be 10 digits")
        return v


def _require_salon(db, salon_id: str):
    resp = db.table("salons").eq("id", salon_id).execute()
    if not resp["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")


@router.post("/{salon_id}/staff", response_model=StaffResponse)
def create_staff(salon_id: str, staff: StaffCreate):
    db = get_db()
    _require_salon(db, salon_id)

    if staff.phone:
        existing = db.table("staff").eq("salon_id", salon_id).eq("phone", staff.phone).execute()
        if any(s.get("is_active") for s in existing["data"]):
            raise HTTPException(status_code=400, detail="Phone already exists in this salon")

    response = db.table("staff").insert(
        {
            "salon_id": salon_id,
            "staff_name": staff.staff_name,
            "phone": staff.phone,
            "is_active": True,
        }
    )
    if not response["data"]:
        raise HTTPException(status_code=400, detail="Insert failed")
    return response["data"][0]


@router.get("/{salon_id}/staff")
def list_staff(salon_id: str, include_inactive: bool = False):
    db = get_db()
    _require_salon(db, salon_id)

    query = db.table("staff").eq("salon_id", salon_id)
    if not include_inactive:
        query = query.eq("is_active", "true")
    return query.order("staff_name").execute()["data"]


@router.patch("/{salon_id}/staff/{staff_id}", response_model=StaffResponse)
def update_staff(salon_id: str, staff_id: str, data: StaffUpdate):
    db = get_db()
    staff_response = db.table("staff").eq("id", staff_id).eq("salon_id", salon_id).execute()
    if not staff_response["data"]:
        raise HTTPException(status_code=404, detail="Staff not found")

    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        return staff_response["data"][0]

    result = db.table("staff").eq("id", staff_id).update(updates)
    if not result["data"]:
        raise HTTPException(status_code=400, detail="Update failed")
    return result["data"][0]


@router.delete("/{salon_id}/staff/{staff_id}")
def delete_staff(salon_id: str, staff_id: str):
    db = get_db()
    staff_response = db.table("staff").eq("id", staff_id).eq("salon_id", salon_id).execute()
    if not staff_response["data"]:
        raise HTTPException(status_code=404, detail="Staff not found")

    db.table("staff").eq("id", staff_id).update({"is_active": False})
    return {"message": "Staff deleted"}
