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

from config import DEBUG, SUPABASE_INVOICE_BUCKET, now_ist
from services import booking, images, invoicing, payments, storage
from services.auth import verify_twilio_signature
from services.booking import BookingError
from services.database import DBError, get_db
from services.invoicing import InvoiceError
from services.messaging import send_whatsapp
from services.session import Session

logger = logging.getLogger("ping.webhook")
router = APIRouter()

RESTART_WORDS = {"HI", "HELLO", "HEY", "MENU", "BOOK", "START"}
STOP_WORDS = {"STOP", "UNSUBSCRIBE"}
MAX_SALONS = 10
MIN_INVOICE_PAISE = 100


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """Receive WhatsApp messages from Twilio and reply."""
    try:
        raw_body = await request.body()
        if not await verify_twilio_signature(request, raw_body):
            logger.warning("Rejected webhook request with invalid Twilio signature")
            return {"status": "forbidden"}

        form = await request.form()
        from_number = form.get("From")
        message_body = (form.get("Body") or "").strip()

        if not from_number or not message_body:
            return {"status": "ignored"}

        phone = normalize_phone(from_number)
        logger.info("WhatsApp in: %s: %s", phone, message_body[:60])
        try:
            response = route_message(phone, message_body)
        except DBError as exc:
            logger.error("DB error in webhook: %s", exc)
            response = "Sorry, we're having a temporary issue. Please try again in a moment."
        except Exception as exc:
            logger.exception("Unhandled error processing message")
            response = (
                f"Something went wrong ({type(exc).__name__}: {exc}). Send *HI* to start over."
                if DEBUG
                else "Something went wrong. Send *HI* to start over."
            )

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
        return handle_owner_message(db, salon["data"][0], phone, message)
    return handle_customer_flow(db, phone, message)


# --------------------------------------------------------------------------- #
# Owner side: read commands + the guided BILL flow + PAID confirmation
# --------------------------------------------------------------------------- #
def handle_owner_message(db, salon: dict, phone: str, message: str) -> str:
    session = Session(phone)
    state = session.get()
    text = message.strip()
    upper = text.upper()

    if upper == "CANCEL":
        session.delete()
        return "Cancelled. Send *BILL* to make an invoice, or *STATS* / *TOMORROW* / *UNPAID*."

    # Continue an in-progress BILL flow before treating the text as a command.
    if state and state.get("owner_step"):
        handler = OWNER_BILL_HANDLERS.get(state["owner_step"])
        if handler:
            return handler(db, session, state, salon, text)
        session.delete()

    return handle_owner_command(db, session, salon, text)


def handle_owner_command(db, session: Session, salon: dict, command: str) -> str:
    salon_id = salon["id"]
    cmd = command.upper().strip()

    if cmd == "BILL":
        return _bill_start(db, session, salon)

    if cmd.startswith("PAID"):
        return _owner_confirm_paid(db, salon, cmd)

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

    return (
        "Commands:\n"
        "• *BILL* — create & send an invoice\n"
        "• *STATS* — today's bookings\n"
        "• *TOMORROW* — tomorrow's schedule\n"
        "• *UNPAID* — outstanding invoices"
    )


def _id_map(db, salon_id: str, table: str, name_field: str) -> dict:
    rows = db.table(table).eq("salon_id", salon_id).execute()["data"]
    return {r["id"]: r.get(name_field) for r in rows}


# --------------------------------------------------------------------------- #
# Owner BILL flow (guided invoice creation) + PAID confirmation
# --------------------------------------------------------------------------- #
def _parse_rupees_to_paise(text: str) -> int | None:
    """`"1200"` / `"1,200.50"` / `"₹1200"` -> paise, or None if invalid/too small."""
    cleaned = text.strip().replace("₹", "").replace(",", "").replace("Rs.", "").replace("rs", "")
    try:
        paise = int(round(float(cleaned) * 100))
    except ValueError:
        return None
    return paise if paise >= MIN_INVOICE_PAISE else None


def _bill_start(db, session: Session, salon: dict) -> str:
    """List today's appointments to bill, plus a walk-in option."""
    salon_id = salon["id"]
    today = now_ist().date()
    appts = (
        db.table("appointments")
        .eq("salon_id", salon_id)
        .eq("appointment_date", str(today))
        .order("appointment_time")
        .execute()["data"]
    )
    appts = [a for a in appts if a["status"] in ("confirmed", "completed")]
    services = _id_map(db, salon_id, "services", "service_name")
    prices = {s["id"]: s["price"] for s in db.table("services").eq("salon_id", salon_id).execute()["data"]}
    customers = db.table("customers").eq("salon_id", salon_id).execute()["data"]
    cust_by_id = {c["id"]: c for c in customers}

    options = []
    lines = ["🧾 Who are you billing? Reply with a number:"]
    for i, a in enumerate(appts, 1):
        cust = cust_by_id.get(a["customer_id"], {})
        svc_name = services.get(a["service_id"], "Service")
        price = prices.get(a["service_id"], 0)
        options.append(
            {
                "customer_id": a["customer_id"],
                "customer_name": cust.get("customer_name", "Customer"),
                "appointment_id": a["id"],
                "description": svc_name,
                "default_amount": price,
            }
        )
        lines.append(f"{i}. {cust.get('customer_name', 'Customer')} — {svc_name} (₹{price / 100:,.0f})")
    lines.append("0. Other (enter a phone number)")

    session.set({"owner_step": "bill_pick", "salon_id": salon_id, "bill_options": options})
    return "\n".join(lines) + "\n\nReply *CANCEL* to stop."


def _bill_pick(db, session, state, salon, text) -> str:
    if text.strip() == "0":
        session.update({"owner_step": "bill_phone"})
        return "Send the customer's 10-digit phone number."

    options = state.get("bill_options", [])
    idx = _pick(text, options)
    if idx is None:
        return "Please reply with a number from the list, or *0* for a walk-in."
    chosen = options[idx]
    session.update(
        {
            "owner_step": "bill_amount",
            "bill_customer_id": chosen["customer_id"],
            "bill_customer_name": chosen["customer_name"],
            "bill_appointment_id": chosen.get("appointment_id"),
            "bill_description": chosen["description"],
            "bill_default_amount": chosen.get("default_amount") or 0,
        }
    )
    default = chosen.get("default_amount") or 0
    hint = f" (reply *OK* for ₹{default / 100:,.0f})" if default >= MIN_INVOICE_PAISE else ""
    return f"Amount for {chosen['customer_name']}? Send the rupee amount{hint}."


def _bill_phone(db, session, state, salon, text) -> str:
    phone = re.sub(r"\D", "", text)[-10:]
    if len(phone) != 10:
        return "That doesn't look right. Send a 10-digit phone number, or *CANCEL*."
    customer = booking.get_or_create_customer(db, state["salon_id"], phone, "Customer")
    session.update(
        {
            "owner_step": "bill_amount",
            "bill_customer_id": customer["id"],
            "bill_customer_name": customer.get("customer_name", "Customer"),
            "bill_appointment_id": None,
            "bill_description": "Salon service",
            "bill_default_amount": 0,
        }
    )
    return "Got it. What's the amount? Send the rupee amount."


def _bill_amount(db, session, state, salon, text) -> str:
    default = state.get("bill_default_amount") or 0
    if text.strip().upper() == "OK" and default >= MIN_INVOICE_PAISE:
        amount = default
    else:
        amount = _parse_rupees_to_paise(text)
        if amount is None:
            return "Please send a valid amount in rupees (at least ₹1), e.g. *500*."
    session.update({"owner_step": "bill_status", "bill_amount": amount})
    return (
        f"₹{amount / 100:,.0f} for {state['bill_customer_name']}. How was it paid?\n"
        "1. UPI (already paid)\n2. Cash (already paid)\n3. Not paid yet (send pay link)"
    )


def _bill_status(db, session, state, salon, text) -> str:
    choice = text.strip()
    if choice not in ("1", "2", "3"):
        return "Reply *1* (UPI), *2* (Cash), or *3* (Not paid yet)."
    payment_status = "unpaid" if choice == "3" else "paid"

    try:
        invoice = invoicing.create_invoice(
            db,
            salon_id=state["salon_id"],
            customer_id=state["bill_customer_id"],
            amount=state["bill_amount"],
            description=state.get("bill_description"),
            appointment_id=state.get("bill_appointment_id"),
            payment_status=payment_status,
        )
    except InvoiceError as exc:
        session.delete()
        return f"⚠️ Couldn't create the invoice: {exc}\nSend *BILL* to try again."

    customer = db.table("customers").eq("id", state["bill_customer_id"]).execute()["data"]
    customer = customer[0] if customer else {}
    pdf_url = invoicing.generate_and_store_pdf(db, salon, invoice, customer)
    _send_invoice_to_customer(salon, invoice, customer, payment_status, pdf_url)

    session.delete()
    code = payments.invoice_code(invoice["id"])
    name = state["bill_customer_name"]
    paid_note = "Marked PAID." if payment_status == "paid" else "Pay link sent to the customer."
    return f"✅ Invoice INV-{code} for ₹{state['bill_amount'] / 100:,.0f} sent to {name}. {paid_note}"


def _send_invoice_to_customer(salon, invoice, customer, payment_status, pdf_url) -> None:
    """DM the customer their invoice with a pay link (if unpaid) and the PDF."""
    phone = customer.get("phone")
    if not phone:
        return
    code = payments.invoice_code(invoice["id"])
    lines = [
        f"🧾 Invoice INV-{code} from *{salon.get('salon_name', 'your salon')}*",
        f"{invoice.get('description') or 'Salon service'} — ₹{invoice['amount'] / 100:,.0f}",
    ]
    if payment_status == "paid":
        lines.append("Status: PAID ✅ Thank you!")
    else:
        lines.append(f"Tap to pay 👉 {payments.pay_url(invoice['id'])}")
        lines.append("After paying, reply *PAID* and we'll confirm.")
    if pdf_url:
        lines.append(f"📄 Invoice: {pdf_url}")
    send_whatsapp(f"+91{phone}", "\n".join(lines), media_url=pdf_url)


def _owner_confirm_paid(db, salon, cmd: str) -> str:
    """Owner replies `PAID <code>` to confirm a customer's payment."""
    parts = cmd.split()
    if len(parts) < 2:
        return "To confirm a payment, reply *PAID <code>* (the code from the alert)."
    code = parts[1].replace("INV-", "").strip().lower()

    unpaid = (
        db.table("invoices").eq("salon_id", salon["id"]).eq("payment_status", "unpaid").execute()["data"]
    )
    match = next((inv for inv in unpaid if payments.invoice_code(inv["id"]).lower() == code), None)
    if not match:
        return f"No unpaid invoice matches code {code.upper()}. Send *UNPAID* to see what's outstanding."

    db.table("invoices").eq("id", match["id"]).update(
        {"payment_status": "paid", "paid_at": now_ist().isoformat()}
    )
    customer = db.table("customers").eq("id", match["customer_id"]).execute()["data"]
    if customer and customer[0].get("phone"):
        send_whatsapp(
            f"+91{customer[0]['phone']}",
            f"✅ Payment confirmed for INV-{payments.invoice_code(match['id'])}. "
            f"Thank you for visiting *{salon.get('salon_name', 'us')}*! 🙏",
        )
    return f"✅ INV-{payments.invoice_code(match['id'])} marked paid (₹{match['amount'] / 100:,.0f})."


OWNER_BILL_HANDLERS = {
    "bill_pick": _bill_pick,
    "bill_phone": _bill_phone,
    "bill_amount": _bill_amount,
    "bill_status": _bill_status,
}


# --------------------------------------------------------------------------- #
# Customer booking flow
# --------------------------------------------------------------------------- #
def handle_customer_flow(db, phone: str, message: str) -> str:
    session = Session(phone)
    state = session.get()
    text = message.strip()
    upper = text.upper()

    if upper == "CANCEL":
        if state:
            # Cancel the in-progress booking flow.
            session.delete()
            return "No problem — booking cancelled. Send *HI* anytime to start again."
        # No active flow — try to cancel their next confirmed appointment.
        return _customer_cancel_confirmed(db, phone)

    if upper in {"MY BOOKING", "MY BOOKINGS", "MYBOOKING"}:
        return _customer_view_bookings(db, phone)

    if upper == "HELP":
        return (
            "Here's what you can do:\n\n"
            "• *HI* — book an appointment\n"
            "• *MY BOOKING* — see your upcoming booking\n"
            "• *CANCEL* — cancel your next booking\n"
            "• *PAID* — confirm a payment to the salon\n"
            "• *STOP* — unsubscribe from offers"
        )

    if upper in STOP_WORDS:
        return _handle_stop(db, phone)

    if upper == "PAID":
        return _customer_reports_paid(db, phone)

    step = state.get("step") if state else None

    # Don't let a stray "HI" nuke an almost-complete booking at the confirm step —
    # just re-show the confirm/cancel prompt instead of starting all over.
    if step == "confirm" and upper in RESTART_WORDS:
        return _confirm_summary(state, state["appt_time"], state.get("customer_name", "there"))

    if not state or upper in RESTART_WORDS:
        return _start(db, session, phone)

    handlers = {
        "choose_salon": _step_salon,
        "choose_service": _step_service,
        "choose_date": _step_date,
        "choose_time": _step_time,
        "choose_staff": _step_staff,
        "ask_name": _step_name,
        "confirm": _step_confirm,
    }
    handler = handlers.get(step)
    if not handler:
        session.delete()
        return _start(db, session, phone)
    return handler(db, session, state, phone, text)


def _customer_cancel_confirmed(db, phone: str) -> str:
    """Cancel the customer's next confirmed upcoming appointment."""
    customers = db.table("customers").eq("phone", phone).execute()["data"]
    if not customers:
        return "You don't have any upcoming bookings with us. Send *HI* to make one."

    today = str(now_ist().date())
    upcoming = []
    for cust in customers:
        appts = (
            db.table("appointments")
            .eq("customer_id", cust["id"])
            .eq("status", "confirmed")
            .gte("appointment_date", today)
            .order("appointment_date")
            .order("appointment_time")
            .execute()["data"]
        )
        for a in appts:
            a["_customer"] = cust
        upcoming.extend(appts)

    if not upcoming:
        return "You have no upcoming bookings to cancel. Send *HI* to book."

    # Cancel the soonest one.
    appt = upcoming[0]
    db.table("appointments").eq("id", appt["id"]).update({"status": "cancelled"})

    salon = db.table("salons").eq("id", appt["salon_id"]).execute()["data"]
    salon = salon[0] if salon else {}
    services = _id_map(db, appt["salon_id"], "services", "service_name")
    appt_date = booking.parse_date(appt["appointment_date"])

    # Notify the owner.
    if salon.get("owner_phone"):
        cust_name = appt["_customer"].get("customer_name", "A customer")
        send_whatsapp(
            f"+91{salon['owner_phone']}",
            f"❌ Cancellation: {cust_name} cancelled their "
            f"{services.get(appt['service_id'], 'appointment')} on "
            f"{appt_date.strftime('%a %d %b')} at {_fmt_time(appt['appointment_time'])}.",
        )

    return (
        f"✅ Booking cancelled:\n"
        f"📅 {appt_date.strftime('%a %d %b')} at {_fmt_time(appt['appointment_time'])}\n"
        f"💇 {services.get(appt['service_id'], 'Appointment')} @ "
        f"{salon.get('salon_name', 'the salon')}\n\n"
        f"Hope to see you another time! Send *HI* to rebook."
    )


def _customer_view_bookings(db, phone: str) -> str:
    """Show the customer their upcoming confirmed appointments."""
    customers = db.table("customers").eq("phone", phone).execute()["data"]
    if not customers:
        return "You have no upcoming bookings. Send *HI* to make one!"

    today = str(now_ist().date())
    upcoming = []
    for cust in customers:
        appts = (
            db.table("appointments")
            .eq("customer_id", cust["id"])
            .eq("status", "confirmed")
            .gte("appointment_date", today)
            .order("appointment_date")
            .order("appointment_time")
            .limit(5)
            .execute()["data"]
        )
        upcoming.extend(appts)

    if not upcoming:
        return "No upcoming bookings. Send *HI* to make one! 😊"

    lines = [f"📅 Your upcoming booking{'s' if len(upcoming) > 1 else ''}:\n"]
    for appt in upcoming[:3]:
        salon = db.table("salons").eq("id", appt["salon_id"]).execute()["data"]
        salon_name = salon[0]["salon_name"] if salon else "Salon"
        services = _id_map(db, appt["salon_id"], "services", "service_name")
        staff = _id_map(db, appt["salon_id"], "staff", "staff_name")
        appt_date = booking.parse_date(appt["appointment_date"])
        lines.append(
            f"• {appt_date.strftime('%a %d %b')} at {_fmt_time(appt['appointment_time'])}\n"
            f"  {services.get(appt['service_id'], 'Service')} with "
            f"{staff.get(appt['staff_id'], 'Stylist')}\n"
            f"  @ {salon_name}"
        )

    lines.append("\nTo cancel your next booking, reply *CANCEL*.")
    return "\n".join(lines)


def _handle_stop(db, phone: str) -> str:
    """Opt the customer out of broadcasts across every salon they belong to."""
    customers = db.table("customers").eq("phone", phone).execute()["data"]
    for c in customers:
        if not c.get("opted_out_broadcasts"):
            db.table("customers").eq("id", c["id"]).update({"opted_out_broadcasts": True})
    return "You've been unsubscribed from offers. You can still book anytime — just send *HI*."


def _customer_reports_paid(db, phone: str) -> str:
    """Customer texted PAID: alert the salon owner to confirm their latest invoice."""
    customers = db.table("customers").eq("phone", phone).execute()["data"]
    if not customers:
        return "We couldn't find your details. Please check with the salon about your payment."
    cust_by_id = {c["id"]: c for c in customers}
    ids = list(cust_by_id.keys())

    invoices = (
        db.table("invoices").in_("customer_id", ids).eq("payment_status", "unpaid").execute()["data"]
    )
    if not invoices:
        return "We don't see a pending invoice for your number. If you just paid, thank you! 🙏"

    invoices.sort(key=lambda i: i.get("created_at") or "", reverse=True)
    inv = invoices[0]
    code = payments.invoice_code(inv["id"])
    cust = cust_by_id.get(inv["customer_id"], {})
    salon = db.table("salons").eq("id", inv["salon_id"]).execute()["data"]
    salon = salon[0] if salon else {}

    if salon.get("owner_phone"):
        send_whatsapp(
            f"+91{salon['owner_phone']}",
            f"💰 {cust.get('customer_name', 'A customer')} says they paid "
            f"₹{inv['amount'] / 100:,.0f} for INV-{code}.\nReply *PAID {code}* to confirm.",
        )
    return "Thanks! We've let the salon know — they'll confirm your payment shortly. 🙏"


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
    # Ask for the DAY next (then time, then stylist) — the customer cares about
    # when they can come in, not which stylist is free for which slot.
    session.update({"step": "choose_date", "service_id": service_id})
    return _date_menu(db, session, state["salon_id"])


def _staff_menu_at_time(db, session, state) -> str:
    """List only the stylists free at the chosen time, plus 'Any available'."""
    meta = state["service_meta"][state["service_id"]]
    settings = state.get("_settings") or booking.get_settings(db, state["salon_id"])
    appt_date = booking.parse_date(state["appt_date"])
    appt_time = booking.parse_time(state["appt_time"])
    free = booking.free_staff_at(db, state["salon_id"], appt_date, appt_time, meta["duration"], settings)
    if not free:
        # The slot filled up between listing and now — send them back to days.
        session.update({"step": "choose_date"})
        return "Oops, that time just filled up 😕.\n\n" + _date_menu(db, session, state["salon_id"])

    session.update(
        {
            "staff_options": [s["id"] for s in free],
            "staff_names": {s["id"]: s["staff_name"] for s in free},
        }
    )
    menu = "Pick your stylist:\n"
    for i, s in enumerate(free, 1):
        menu += f"{i}. {s['staff_name']}\n"
    menu += "0. Any available\n"
    return menu + "\nReply with the number."


def _step_staff(db, session, state, phone, text) -> str:
    options = state.get("staff_options", [])
    if text.strip() == "0":
        if not options:
            return "Please pick a stylist from the list."
        staff_id = options[0]  # "Any available" -> first free stylist
    else:
        idx = _pick(text, options)
        if idx is None:
            return "Please reply with a stylist's number, or *0* for any available."
        staff_id = options[idx]

    session.update({"staff_id": staff_id})
    state = session.get()  # refresh so confirm/summary sees staff_id

    # Skip the name prompt if we already know this customer.
    existing = db.table("customers").eq("salon_id", state["salon_id"]).eq("phone", phone).execute()["data"]
    known_name = existing[0]["customer_name"] if existing else None
    if known_name and known_name.strip().lower() != "customer":
        session.update({"step": "confirm", "customer_name": known_name})
        return _confirm_summary(session.get(), state["appt_time"], known_name)

    session.update({"step": "ask_name"})
    return "Almost done! What's your name?"


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
    slots = booking.available_slots_any_staff(
        db, state["salon_id"], appt_date, meta["duration"], settings
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
    session.update({"step": "choose_staff", "appt_time": appt_time})
    return _staff_menu_at_time(db, session, session.get())


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
        if (customer.get("customer_name") or "").strip().lower() == "customer" and name != "Customer":
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
    confirmation = (
        f"✅ Booking confirmed, {name}!\n\n"
        f"{meta['name']} with {staff_name}\n"
        f"{appt_date.strftime('%a %d %b')} at {_fmt_time(state['appt_time'])}\n\n"
        f"See you soon! Send *HI* to book again."
    )

    # Best-effort: attach a shareable confirmation card. Never let an image
    # failure break a successful booking — fall back to the text message.
    try:
        card = images.generate_booking_image(
            state.get("salon_name") or "Salon",
            name,
            meta["name"],
            staff_name,
            appt_date.strftime("%a %d %b %Y"),
            _fmt_time(state["appt_time"]),
        )
        path = f"bookings/{salon_id}/{phone}-{appt_date}-{state['appt_time']}.png"
        url = storage.upload_bytes(SUPABASE_INVOICE_BUCKET, path, card, "image/png")
        if url:
            send_whatsapp(f"+91{phone}", confirmation, media_url=url)
            return ""  # already sent (with the image); avoid a duplicate text
    except Exception:
        logger.exception("Booking confirmation image failed; sending text only")

    return confirmation


def _fmt_time(value) -> str:
    """`"14:00"` / `"14:00:00"` -> `"2:00 PM"`."""
    text = str(value)
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).strftime("%I:%M %p").lstrip("0")
        except ValueError:
            continue
    return text
