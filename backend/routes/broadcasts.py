import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, UploadFile, File
from pydantic import BaseModel

from config import SUPABASE_INVOICE_BUCKET
from models.broadcaste import BroadcastCreate, BroadcastResponse
from services import storage
from services.banners import generate_offer_banner
from services.database import get_db
from services.messaging import send_whatsapp

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB (Twilio limit)

logger = logging.getLogger("ping.broadcasts")
router = APIRouter()


class BroadcastUpdate(BaseModel):
    message_text: Optional[str] = None
    image_url: Optional[str] = None


class SendRequest(BaseModel):
    customer_ids: Optional[list[str]] = None


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


@router.post("/{salon_id}/broadcasts/upload-image")
async def upload_broadcast_image(salon_id: str, file: UploadFile = File(...)):
    """Upload an image to Supabase and return a public URL usable in broadcasts."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type. Allowed: jpeg, png, webp, gif.")

    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image too large. Max 5 MB.")

    ext = (file.filename or "image").rsplit(".", 1)[-1].lower()
    path = f"banners/{salon_id}/{uuid.uuid4()}.{ext}"
    public_url = storage.upload_bytes(SUPABASE_INVOICE_BUCKET, path, data, file.content_type)

    if not public_url:
        raise HTTPException(status_code=500, detail="Image upload failed. Check Supabase storage is configured.")

    return {"url": public_url}


@router.post("/{salon_id}/broadcasts", response_model=BroadcastResponse)
def create_broadcast(salon_id: str, broadcast: BroadcastCreate):
    db = get_db()
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    salon = salon_response["data"][0]

    image_url = broadcast.image_url
    if broadcast.headline:
        try:
            png = generate_offer_banner(
                salon.get("salon_name", "Salon"), broadcast.headline, broadcast.subtext
            )
            path = f"banners/{salon_id}/{abs(hash(broadcast.headline)) % 10_000_000}.png"
            uploaded = storage.upload_bytes(SUPABASE_INVOICE_BUCKET, path, png, "image/png")
            if uploaded:
                image_url = uploaded
            else:
                logger.warning("Banner upload failed for salon %s; sending without image", salon_id)
        except Exception as exc:  # pragma: no cover
            logger.error("Banner generation failed for salon %s: %s", salon_id, exc)

    response = db.table("broadcasts").insert(
        {
            "salon_id": salon_id,
            "message_text": broadcast.message_text,
            "image_url": image_url,
            "sent_count": 0,
        }
    )
    if not response["data"]:
        raise HTTPException(status_code=400, detail="Insert failed")
    return response["data"][0]


@router.patch("/{salon_id}/broadcasts/{broadcast_id}", response_model=BroadcastResponse)
def update_broadcast(salon_id: str, broadcast_id: str, data: BroadcastUpdate):
    db = get_db()
    bc_response = db.table("broadcasts").eq("id", broadcast_id).eq("salon_id", salon_id).execute()
    if not bc_response["data"]:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        return bc_response["data"][0]

    result = db.table("broadcasts").eq("id", broadcast_id).update(updates)
    if not result["data"]:
        raise HTTPException(status_code=400, detail="Update failed")
    return result["data"][0]


@router.post("/{salon_id}/broadcasts/{broadcast_id}/send")
def send_broadcast(
    salon_id: str,
    broadcast_id: str,
    background_tasks: BackgroundTasks,
    body: Optional[SendRequest] = Body(None),
    limit: int | None = None,
):
    db = get_db()

    broadcast_response = (
        db.table("broadcasts").eq("id", broadcast_id).eq("salon_id", salon_id).execute()
    )
    if not broadcast_response["data"]:
        raise HTTPException(status_code=404, detail="Broadcast not found")
    broadcast = broadcast_response["data"][0]

    customers_response = db.table("customers").eq("salon_id", salon_id).execute()
    all_opted_in = [c for c in customers_response["data"] if not c.get("opted_out_broadcasts")]

    if body and body.customer_ids:
        id_set = set(body.customer_ids)
        recipients = [c for c in all_opted_in if c["id"] in id_set]
    else:
        recipients = all_opted_in

    if limit:
        recipients = recipients[:limit]

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
