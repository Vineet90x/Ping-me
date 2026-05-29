"""WhatsApp webhook + conversational booking flow.

Fixes the earlier hardcoded prototype:
  * salons, services, staff are all fetched live and selected by the number the
    customer actually types (no more "always book the first one");
  * real calendar dates instead of a hardcoded date;
  * time slots computed from business hours, service duration and existing
    bookings (no double-booking);
  * the customer's name is collected on first booking;
  * owner STATS / TOMORROW / UNPAID return real data.
"""
import logging
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Request

from config import now_ist
from services import booking
from services.booking import BookingError
from services.database import DBError, get_db
from services.messaging import send_whatsapp
from services.session import Session

logger = logging.getLogger("ping.webhook")
router = APIRouter()

RESTART_WORDS = {"HI", "HELLO", "HEY", "MENU", "BOOK", "START"}
MAX_SALONS = 10


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """Receive WhatsApp messages from Twilio and reply."""
    try:
        form = await request.form()
        from_number = form.get("From")
        message_body = (form.get("Body") or "").strip()

        if not from_number or not message_body:
            return {"status": "ignored"}

        phone = normalize_phone(from_number)
        try:
            response = route_message(phone, message_body)
        except DBError as exc:
            logger.error("DB error in webhook: %s", exc)
            response = "Sorry, we're having a temporary issue. Please try again in a moment."
        except Exception:
            logger.exception("Unhandled error processing message")
            response = "Something went wrong. Send *HI* to start over."

        if response:
            send_whatsapp(from_number, response)
        return {"status": "ok"}
    except Exception:
        logger.exception("Fatal webhook error")
        return {"status": "error"}


def normalize_phone(raw: str) -> str:
    """`whatsapp:+919136275825` -> `9136275825` (last 10 digits)."""
    digits = re.sub(r"\D", "", raw or "")
    return digits[-10:] if len(digits) >= 10 else digits


def route_message(phone: str, message: str) -> str:
    db = get_db()
    salon = db.table("salons").eq("owner_phone", phone).execute()
    if salon["data"]:
        return handle_owner_command(salon["data"][0], message)
    return handle_customer_flow(db, phone, message)


# --------------------------------------------------------------------------- #
# Owner commands
# --------------------------------------------------------------------------- #
def handle_owner_command(salon: dict, command: str) -> str:
    db = get_db()
    salon_id = salon["id"]
    cmd = command.upper().strip()

    if cmd == "STATS":
        today = now_ist().date()
        appts = (
            db.table("appointments").eq("salon_id", salon_id).eq("appointment_date", str(today)).execute()["data"]
        )
        confirmed = sum(1 for a in appts if a["status"] == "confirmed")
        completed = sum(1 for a in appts if a["status"] == "completed")
        cancelled = sum(1 for a in appts if a["status"] in ("cancelled", "no_show"))
        return (
            f"📊 Today ({today.strftime('%d %b')})\n"
            f"Upcoming: {confirmed}\nCompleted: {completed}\nCancelled/No-show: {cancelled}"
        )

    if cmd == "TOMORROW":
        tomorrow = (now_ist() + timedelta(days=1)).date()
        appts = (
            db.table("appointments")
            .eq("salon_id", salon_id)
            .eq("appointment_date", str(tomorrow))
            .order("appointment_time")
            .execute()["data"]
        )
        active = [a for a in appts if a["status"] == "confirmed"]
        if not active:
            return f"No appointments tomorrow ({tomorrow.strftime('%d %b')}). Enjoy the break!"
        services = _id_map(db, salon_id, "services", "service_name")
        staff = _id_map(db, salon_id, "staff", "staff_name")
        customers = _id_map(db, salon_id, "customers", "customer_name")
        lines = [f"📅 Tomorrow ({tomorrow.strftime('%a %d %b')}): {len(active)} booking(s)"]
        for a in active:
            lines.append(
                f"• {_fmt_time(a['appointment_time'])} — "
                f"{services.get(a['service_id'], 'Service')} with "
                f"{staff.get(a['staff_id'], 'staff')} "
                f"({customers.get(a['customer_id'], 'Customer')})"
            )
        return "\n".join(lines)

    if cmd == "UNPAID":
        invoices = (
            db.table("invoices").eq("salon_id", salon_id).eq("payment_status", "unpaid").execute()["data"]
        )
        total = sum(inv["amount"] for inv in invoices)
        return f"💰 Unpaid: {len(invoices)} invoice(s), ₹{total / 100:,.2f} outstanding"

    return "Commands:\n• *STATS* — today's bookings\n• *TOMORROW* — tomorrow's schedule\n• *UNPAID* — outstanding invoices"


def _id_map(db, salon_id: str, table: str, name_field: str) -> dict:
    rows = db.table(table).eq("salon_id", salon_id).execute()["data"]
    return {r["id"]: r.get(name_field) for r in rows}


# --------------------------------------------------------------------------- #
# Customer booking flow
# --------------------------------------------------------------------------- #
def handle_customer_flow(db, phone: str, message: str) -> str:
    session = Session(phone)
    state = session.get()
    text = message.strip()
    upper = text.upper()

    if upper == "CANCEL":
        session.delete()
        return "No problem — booking cancelled. Send *HI* anytime to start again."

    if not state or upper in RESTART_WORDS:
        return _start(db, session, phone)

    step = state.get("step")
    handlers = {
        "choose_salon": _step_salon,
        "choose_service": _step_service,
        "choose_staff": _step_staff,
        "choose_date": _step_date,
        "choose_time": _step_time,
        "ask_name": _step_name,
        "confirm": _step_confirm,
    }
    handler = handlers.get(step)
    if not handler:
        session.delete()
        return _start(db, session, phone)
    return handler(db, session, state, phone, text)


def _pick(text: str, options: list) -> int | None:
    """Return the 0-based index a customer selected, or None if invalid."""
    if not text.isdigit():
        return None
    idx = int(text) - 1
    return idx if 0 <= idx < len(options) else None


def _start(db, session: Session, phone: str) -> str:
    salons = db.table("salons").order("salon_name").limit(MAX_SALONS).execute()["data"]
    if not salons:
        return "No salons are available right now. Please try again later."

    if len(salons) == 1:
        salon = salons[0]
        session.set({"step": "choose_service", "phone": phone, "salon_id": salon["id"], "salon_name": salon["salon_name"]})
        return f"Welcome to *{salon['salon_name']}*! 💇\n\n" + _services_menu(db, session, salon["id"])

    ids = [s["id"] for s in salons]
    names = [s["salon_name"] for s in salons]
    session.set({"step": "choose_salon", "phone": phone, "options": ids, "names": names})
    menu = "Welcome to *Ping*! 💇\n\nChoose a salon:\n"
    menu += "\n".join(f"{i}. {n}" for i, n in enumerate(names, 1))
    return menu + "\n\nReply with the number."


def _step_salon(db, session, state, phone, text) -> str:
    idx = _pick(text, state.get("options", []))
    if idx is None:
        return "Please reply with the number of a salon from the list."
    salon_id = state["options"][idx]
    salon_name = state["names"][idx]
    session.update({"step": "choose_service", "salon_id": salon_id, "salon_name": salon_name})
    return _services_menu(db, session, salon_id)


def _services_menu(db, session, salon_id) -> str:
    services = booking.get_active_services(db, salon_id)
    if not services:
        session.delete()
        return "This salon has no services listed yet. Please try again later."
    session.update(
        {
            "service_options": [s["id"] for s in services],
            "service_meta": {s["id"]: {"name": s["service_name"], "price": s["price"], "duration": s["duration_minutes"]} for s in services},
        }
    )
    menu = "Choose a service:\n"
    for i, s in enumerate(services, 1):
        menu += f"{i}. {s['service_name']} — ₹{s['price'] / 100:,.0f} ({s['duration_minutes']} min)\n"
    return menu + "\nReply with the number."


def _step_service(db, session, state, phone, text) -> str:
    options = state.get("service_options", [])
    idx = _pick(text, options)
    if idx is None:
        return "Please reply with the number of a service from the list."
    service_id = options[idx]
    session.update({"step": "choose_staff", "service_id": service_id})
    return _staff_menu(db, session, state["salon_id"])


def _staff_menu(db, session, salon_id) -> str:
    staff = booking.get_active_staff(db, salon_id)
    if not staff:
        session.delete()
        return "This salon has no stylists available yet. Please try again later."
    session.update(
        {
            "staff_options": [s["id"] for s in staff],
            "staff_names": {s["id"]: s["staff_name"] for s in staff},
        }
    )
    menu = "Choose a stylist:\n"
    for i, s in enumerate(staff, 1):
        menu += f"{i}. {s['staff_name']}\n"
    return menu + "\nReply with the number."


def _step_staff(db, session, state, phone, text) -> str:
    options = state.get("staff_options", [])
    idx = _pick(text, options)
    if idx is None:
        return "Please reply with the number of a stylist from the list."
    staff_id = options[idx]
    session.update({"step": "choose_date", "staff_id": staff_id})
    return _date_menu(db, session, state["salon_id"])


def _date_menu(db, session, salon_id) -> str:
    settings = booking.get_settings(db, salon_id)
    days = min(int(settings["days_advance_booking"]), 7)
    today = now_ist().date()
    dates = [today + timedelta(days=i) for i in range(days)]
    session.update({"date_options": [str(d) for d in dates], "_settings": settings})
    menu = "Choose a day:\n"
    for i, d in enumerate(dates, 1):
        label = "Today" if i == 1 else ("Tomorrow" if i == 2 else d.strftime("%a"))
        menu += f"{i}. {label}, {d.strftime('%d %b')}\n"
    return menu + "\nReply with the number."


def _step_date(db, session, state, phone, text) -> str:
    options = state.get("date_options", [])
    idx = _pick(text, options)
    if idx is None:
        return "Please reply with the number of a day from the list."
    appt_date = booking.parse_date(options[idx])
    meta = state["service_meta"][state["service_id"]]
    settings = state.get("_settings") or booking.get_settings(db, state["salon_id"])
    slots = booking.available_slots(
        db, state["salon_id"], state["staff_id"], appt_date, meta["duration"], settings
    )
    if not slots:
        return "No free slots that day 😕. Please reply with another day's number."

    slot_strs = [s.strftime("%H:%M") for s in slots]
    session.update({"step": "choose_time", "appt_date": options[idx], "time_options": slot_strs})
    menu = f"Available times on {appt_date.strftime('%a %d %b')}:\n"
    for i, t in enumerate(slot_strs, 1):
        menu += f"{i}. {_fmt_time(t)}\n"
    return menu + "\nReply with the number."


def _step_time(db, session, state, phone, text) -> str:
    options = state.get("time_options", [])
    idx = _pick(text, options)
    if idx is None:
        return "Please reply with the number of a time from the list."
    appt_time = options[idx]

    # Skip asking for a name if we already know this customer.
    existing = db.table("customers").eq("salon_id", state["salon_id"]).eq("phone", phone).execute()["data"]
    known_name = existing[0]["customer_name"] if existing else None
    if known_name and known_name.strip().lower() != "customer":
        session.update({"step": "confirm", "appt_time": appt_time, "customer_name": known_name})
        return _confirm_summary(state, appt_time, known_name)

    session.update({"step": "ask_name", "appt_time": appt_time})
    return "Almost done! What's your name?"


def _step_name(db, session, state, phone, text) -> str:
    name = text.strip()
    if len(name) < 2:
        return "Please send your name (at least 2 letters)."
    session.update({"step": "confirm", "customer_name": name})
    return _confirm_summary(state, state["appt_time"], name)


def _confirm_summary(state, appt_time, name) -> str:
    meta = state["service_meta"][state["service_id"]]
    staff_name = state["staff_names"][state["staff_id"]]
    appt_date = booking.parse_date(state["appt_date"])
    return (
        f"Please confirm your booking, {name}:\n\n"
        f"💇 Service: {meta['name']} (₹{meta['price'] / 100:,.0f})\n"
        f"✂️ Stylist: {staff_name}\n"
        f"📅 Date: {appt_date.strftime('%a %d %b %Y')}\n"
        f"🕐 Time: {_fmt_time(appt_time)}\n\n"
        f"Reply *CONFIRM* to book, or *CANCEL* to stop."
    )


def _step_confirm(db, session, state, phone, text) -> str:
    if text.upper().strip() != "CONFIRM":
        return "Reply *CONFIRM* to book, or *CANCEL* to stop."

    salon_id = state["salon_id"]
    meta = state["service_meta"][state["service_id"]]
    service = {"id": state["service_id"], "duration_minutes": meta["duration"]}
    appt_date = booking.parse_date(state["appt_date"])
    appt_time = booking.parse_time(state["appt_time"])
    name = state.get("customer_name", "Customer")

    try:
        customer = booking.get_or_create_customer(db, salon_id, phone, name)
        if customer.get("customer_name", "").strip().lower() == "customer" and name != "Customer":
            db.table("customers").eq("id", customer["id"]).update({"customer_name": name})
        booking.create_appointment(
            db,
            salon_id=salon_id,
            customer_id=customer["id"],
            staff_id=state["staff_id"],
            service=service,
            appt_date=appt_date,
            appt_time=appt_time,
        )
    except BookingError as exc:
        # Let them retry the time without losing the rest of the booking.
        session.update({"step": "choose_date"})
        return f"⚠️ {exc}\n\n" + _date_menu(db, session, salon_id)

    session.delete()
    staff_name = state["staff_names"][state["staff_id"]]
    return (
        f"✅ Booking confirmed, {name}!\n\n"
        f"{meta['name']} with {staff_name}\n"
        f"{appt_date.strftime('%a %d %b')} at {_fmt_time(state['appt_time'])}\n\n"
        f"See you soon! Send *HI* to book again."
    )


def _fmt_time(value) -> str:
    """`"14:00"` / `"14:00:00"` -> `"2:00 PM"`."""
    text = str(value)
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).strftime("%I:%M %p").lstrip("0")
        except ValueError:
            continue
    return text
