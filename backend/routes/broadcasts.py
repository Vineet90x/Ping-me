from fastapi import APIRouter, HTTPException
from models.broadcaste import BroadcastCreate, BroadcastResponse
from services.database import get_db

router = APIRouter()

@router.post("/{salon_id}/broadcasts", response_model=BroadcastResponse)
def create_broadcast(salon_id: str, broadcast: BroadcastCreate):
    db = get_db()
    
    # Check salon exists
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    
    # Create broadcast record
    response = db.table("broadcasts").insert({
        "salon_id": salon_id,
        "message_text": broadcast.message_text,
        "image_url": broadcast.image_url,
        "sent_count": 0
    })
    
    if not response["data"]:
        raise HTTPException(status_code=400, detail="Insert failed")
    
    return response["data"][0]

@router.post("/{salon_id}/broadcasts/{broadcast_id}/send")
def send_broadcast(salon_id: str, broadcast_id: str, limit: int = None):
    db = get_db()
    
    broadcast_response = db.table("broadcasts").eq("id", broadcast_id).execute()
    if not broadcast_response["data"]:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    
    customers_response = db.table("customers").eq("salon_id", salon_id).execute()
    customers = [c for c in customers_response["data"] if not c["opted_out_broadcasts"]]
    
    if limit:
        customers = customers[:limit]
    
    sent_count = len(customers)
    
    db.table("broadcasts").eq("id", broadcast_id).update({"sent_count": sent_count})
    
    return {
        "id": broadcast_id,
        "sent_count": sent_count,
        "message": f"Broadcast queued. Sending to {sent_count} customers."
    }

@router.get("/{salon_id}/broadcasts")
def list_broadcasts(salon_id: str):
    db = get_db()
    
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    
    response = db.table("broadcasts").eq("salon_id", salon_id).execute()
    return response["data"] if response["data"] else []