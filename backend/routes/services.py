from fastapi import APIRouter, HTTPException
from models.services import ServiceCreate, ServiceResponse
from services.database import get_db

router = APIRouter()

@router.post("/{salon_id}/services", response_model=ServiceResponse)
def create_service(salon_id: str, service: ServiceCreate):
    db = get_db()
    
    # Check salon exists
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    
    # Check service name uniqueness within salon
    existing = db.table("services").eq("salon_id", salon_id).execute()
    if any(s["service_name"].lower() == service.service_name.lower() for s in existing["data"]):
        raise HTTPException(status_code=400, detail="Service already exists in this salon")
    
    response = db.table("services").insert({
        "salon_id": salon_id,
        "service_name": service.service_name,
        "price": service.price,
        "duration_minutes": service.duration_minutes,
        "is_active": True
    })
    
    if not response["data"]:
        raise HTTPException(status_code=400, detail="Insert failed")
    
    return response["data"][0]

@router.get("/{salon_id}/services")
def list_services(salon_id: str):
    db = get_db()
    
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    
    response = db.table("services").eq("salon_id", salon_id).execute()
    return response["data"] if response["data"] else []

@router.delete("/{salon_id}/services/{service_id}")
def delete_service(salon_id: str, service_id: str):
    db = get_db()
    
    service_response = db.table("services").eq("id", service_id).execute()
    if not service_response["data"]:
        raise HTTPException(status_code=404, detail="Service not found")
    
    db.table("services").eq("id", service_id).update({"is_active": False})
    
    return {"message": "Service deleted"}