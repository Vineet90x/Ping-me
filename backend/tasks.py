"""Celery tasks: appointment reminders and broadcast delivery."""
import logging
from datetime import datetime, timedelta

from celery_app import celery_app
from config import now_ist
from services.database import get_db
from services.messaging import send_whatsapp

logger = logging.getLogger("ping.tasks")

# How close to the appointment the "1 hour" reminder should fire (beat runs /15 min).
ONE_HOUR_WINDOW_MIN = 90


def _names(db, salon_id):
    services = {s["id"]: s["service_name"] for s in db.table("services").eq("salon_id", salon_id).execute()["data"]}
    staff = {s["id"]: s["staff_name"] for s in db.table("staff").eq("salon_id", salon_id).execute()["data"]}
    salon = db.table("salons").eq("id", salon_id).execute()["data"]
    salon_name = salon[0]["salon_name"] if salon else "your salon"
    return services, staff, salon_name


def _fmt_time(value) -> str:
    text = str(value)
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).strftime("%I:%M %p").lstrip("0")
        except ValueError:
            continue
    return text


def _send_reminder(db, appt, when_label: str) -> bool:
    customer = db.table("customers").eq("id", appt["customer_id"]).execute()["data"]
    if not customer or not customer[0].get("phone"):
        return False
    cust = customer[0]
    services, staff, salon_name = _names(db, appt["salon_id"])
    message = (
        f"⏰ Reminder: your appointment at *{salon_name}* is {when_label}.\n\n"
        f"💇 {services.get(appt['service_id'], 'Service')} with "
        f"{staff.get(appt['staff_id'], 'your stylist')}\n"
        f"🕐 {_fmt_time(appt['appointment_time'])}\n\n"
        f"Reply *CANCEL* if you can't make it."
    )
    return send_whatsapp(f"+91{cust['phone']}", message)


@celery_app.task(name="tasks.send_due_reminders")
def send_due_reminders() -> dict:
    """Send 24-hour and 1-hour appointment reminders. Idempotent via flags."""
    db = get_db()
    now = now_ist()
    today = now.date()
    tomorrow = today + timedelta(days=1)
    sent_24h = sent_1h = 0

    # --- 24-hour reminders: everything booked for tomorrow ---
    upcoming = (
        db.table("appointments")
        .eq("appointment_date", str(tomorrow))
        .eq("status", "confirmed")
        .execute()["data"]
    )
    for appt in upcoming:
        if appt.get("reminder_sent_24h"):
            continue
        if _send_reminder(db, appt, "tomorrow"):
            db.table("appointments").eq("id", appt["id"]).update({"reminder_sent_24h": True})
            sent_24h += 1

    # --- 1-hour reminders: today's appointments starting soon ---
    today_appts = (
        db.table("appointments")
        .eq("appointment_date", str(today))
        .eq("status", "confirmed")
        .execute()["data"]
    )
    for appt in today_appts:
        if appt.get("reminder_sent_1h"):
            continue
        try:
            appt_dt = datetime.combine(today, datetime.strptime(str(appt["appointment_time"])[:5], "%H:%M").time())
        except ValueError:
            continue
        minutes_away = (appt_dt - now).total_seconds() / 60
        if 0 <= minutes_away <= ONE_HOUR_WINDOW_MIN:
            if _send_reminder(db, appt, "in about an hour"):
                db.table("appointments").eq("id", appt["id"]).update({"reminder_sent_1h": True})
                sent_1h += 1

    logger.info("Reminders sent: %s (24h), %s (1h)", sent_24h, sent_1h)
    return {"sent_24h": sent_24h, "sent_1h": sent_1h}


@celery_app.task(name="tasks.send_broadcast")
def send_broadcast(broadcast_id: str, salon_id: str) -> dict:
    """Deliver a broadcast to all opted-in customers of a salon."""
    db = get_db()
    broadcast = db.table("broadcasts").eq("id", broadcast_id).execute()["data"]
    if not broadcast:
        return {"error": "broadcast not found"}
    msg = broadcast[0]
    customers = db.table("customers").eq("salon_id", salon_id).execute()["data"]

    sent = 0
    for c in customers:
        if c.get("opted_out_broadcasts") or not c.get("phone"):
            continue
        if send_whatsapp(f"+91{c['phone']}", msg["message_text"], media_url=msg.get("image_url")):
            sent += 1

    db.table("broadcasts").eq("id", broadcast_id).update({"sent_count": sent})
    logger.info("Broadcast %s sent to %s customers", broadcast_id, sent)
    return {"sent": sent}
