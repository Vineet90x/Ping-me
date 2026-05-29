from fastapi import APIRouter, HTTPException

from models.staff import StaffCreate, StaffResponse
from services.database import get_db

router = APIRouter()


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


@router.delete("/{salon_id}/staff/{staff_id}")
def delete_staff(salon_id: str, staff_id: str):
    db = get_db()
    staff_response = db.table("staff").eq("id", staff_id).eq("salon_id", salon_id).execute()
    if not staff_response["data"]:
        raise HTTPException(status_code=404, detail="Staff not found")

    db.table("staff").eq("id", staff_id).update({"is_active": False})
    return {"message": "Staff deleted"}
