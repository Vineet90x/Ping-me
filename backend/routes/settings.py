from fastapi import APIRouter, HTTPException
from models.settings import SettingsUpdate, SettingsResponse
from services.database import get_db

router = APIRouter()

@router.get("/{salon_id}/settings", response_model=SettingsResponse)
def get_settings(salon_id: str):
    db = get_db()
    
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    
    settings_response = db.table("settings").eq("salon_id", salon_id).execute()
    if not settings_response["data"]:
        return {
            "salon_id": salon_id,
            "opening_time": "10:00",
            "closing_time": "20:00",
            "days_advance_booking": 30,
            "min_advance_booking_minutes": 60,
            "max_concurrent": None,
        }

    return settings_response["data"][0]

@router.patch("/{salon_id}/settings")
def update_settings(salon_id: str, settings: SettingsUpdate):
    db = get_db()
    
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    
    update_data = {}
    if settings.opening_time:
        update_data["opening_time"] = str(settings.opening_time)
    if settings.closing_time:
        update_data["closing_time"] = str(settings.closing_time)
    if settings.days_advance_booking:
        update_data["days_advance_booking"] = settings.days_advance_booking
    if settings.min_advance_booking_minutes is not None:
        update_data["min_advance_booking_minutes"] = settings.min_advance_booking_minutes
    if settings.max_concurrent is not None:
        update_data["max_concurrent"] = settings.max_concurrent
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    existing = db.table("settings").eq("salon_id", salon_id).execute()
    
    if existing["data"]:
        db.table("settings").eq("salon_id", salon_id).update(update_data)
    else:
        update_data["salon_id"] = salon_id
        db.table("settings").insert(update_data)
    
    return {"message": "Settings updated"}