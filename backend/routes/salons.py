from fastapi import APIRouter, HTTPException
from models.salon import SalonRegister, SalonResponse, SalonUpdate
from services.database import get_db

router = APIRouter()

@router.post("/register", response_model=SalonResponse)
def register_salon(salon: SalonRegister):
    db = get_db()
    
    existing = db.table("salons").eq("owner_phone", salon.owner_phone).execute()
    if existing["data"]:
        raise HTTPException(status_code=400, detail="Phone already registered")
    
    response = db.table("salons").insert({
        "owner_phone": salon.owner_phone,
        "owner_name": salon.owner_name,
        "salon_name": salon.salon_name,
        "upi_id": salon.upi_id,
        "plan_type": "free"
    })
    
    if not response["data"]:
        raise HTTPException(status_code=400, detail="Insert failed")
    
    return response["data"][0]

@router.get("/{salon_id}")
def get_salon(salon_id: str):
    db = get_db()
    response = db.table("salons").eq("id", salon_id).execute()
    
    if not response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    
    return response["data"][0]

@router.get("/by-phone/{owner_phone}")
def get_salon_by_phone(owner_phone: str):
    db = get_db()
    response = db.table("salons").eq("owner_phone", owner_phone).execute()
    
    if not response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    
    return response["data"][0]

@router.patch("/{salon_id}")
def update_salon(salon_id: str, salon: SalonUpdate):
    db = get_db()
    
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    
    # Only update provided fields
    update_data = {}
    if salon.owner_name:
        update_data["owner_name"] = salon.owner_name
    if salon.salon_name:
        update_data["salon_name"] = salon.salon_name
    if salon.upi_id:
        update_data["upi_id"] = salon.upi_id
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    db.table("salons").eq("id", salon_id).update(update_data)
    
    return {"message": "Salon updated", "updated_fields": update_data}