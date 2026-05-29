import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from models.broadcaste import BroadcastCreate, BroadcastResponse
from services.database import get_db
from services.messaging import send_whatsapp

logger = logging.getLogger("ping.broadcasts")
router = APIRouter()


def _deliver_broadcast(broadcast_id: str, salon_id: str, message: str, image_url: str | None, recipients: list[dict]):
    """Send a broadcast to recipients and record how many actually went out."""
    sent = 0
    for customer in recipients:
        phone = customer.get("phone")
        if not phone:
            continue
        if send_whatsapp(f"+91{phone}", message, media_url=image_url):
            sent += 1
    try:
        get_db().table("broadcasts").eq("id", broadcast_id).update({"sent_count": sent})
    except Exception as exc:  # pragma: no cover
        logger.error("Could not update sent_count for %s: %s", broadcast_id, exc)
    logger.info("Broadcast %s delivered to %s/%s recipients", broadcast_id, sent, len(recipients))


@router.post("/{salon_id}/broadcasts", response_model=BroadcastResponse)
def create_broadcast(salon_id: str, broadcast: BroadcastCreate):
    db = get_db()
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")

    response = db.table("broadcasts").insert(
        {
            "salon_id": salon_id,
            "message_text": broadcast.message_text,
            "image_url": broadcast.image_url,
            "sent_count": 0,
        }
    )
    if not response["data"]:
        raise HTTPException(status_code=400, detail="Insert failed")
    return response["data"][0]


@router.post("/{salon_id}/broadcasts/{broadcast_id}/send")
def send_broadcast(
    salon_id: str, broadcast_id: str, background_tasks: BackgroundTasks, limit: int | None = None
):
    db = get_db()

    broadcast_response = (
        db.table("broadcasts").eq("id", broadcast_id).eq("salon_id", salon_id).execute()
    )
    if not broadcast_response["data"]:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    broadcast = broadcast_response["data"][0]

    customers_response = db.table("customers").eq("salon_id", salon_id).execute()
    recipients = [c for c in customers_response["data"] if not c.get("opted_out_broadcasts")]
    if limit:
        recipients = recipients[:limit]

    # Send in the background so this request returns immediately.
    background_tasks.add_task(
        _deliver_broadcast,
        broadcast_id,
        salon_id,
        broadcast["message_text"],
        broadcast.get("image_url"),
        recipients,
    )

    return {
        "id": broadcast_id,
        "recipients": len(recipients),
        "message": f"Broadcast queued. Sending to {len(recipients)} customers.",
    }


@router.get("/{salon_id}/broadcasts")
def list_broadcasts(salon_id: str):
    db = get_db()
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")

    return db.table("broadcasts").eq("salon_id", salon_id).order("created_at", desc=True).execute()["data"]
