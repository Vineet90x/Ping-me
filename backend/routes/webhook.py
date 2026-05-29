from datetime import datetime

from fastapi import APIRouter, Request

from services.database import get_db
from services.session import Session

router = APIRouter()


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """Receive WhatsApp messages from Twilio."""
    try:
        body = await request.form()
        from_number = body.get("From")
        message_body = body.get("Body")

        if not from_number or not message_body:
            return {"status": "error"}

        customer_phone = from_number.replace("whatsapp:", "").replace("+91", "").replace("+1", "")
        response = route_message(customer_phone, message_body)
        send_whatsapp_response(from_number, response)

        return {"status": "ok"}

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        return {"status": "error"}


def route_message(phone: str, message: str):
    """Determine if the sender is an owner or a customer."""
    db = get_db()
    salon_response = db.table("salons").eq("owner_phone", phone).execute()

    if salon_response["data"]:
        return handle_owner_command(salon_response["data"][0], message)

    return handle_customer_flow(phone, message)


def handle_owner_command(salon: dict, command: str):
    """Handle owner commands."""
    command = command.upper().strip()
    db = get_db()
    salon_id = salon["id"]

    if command == "STATS":
        appointments = db.table("appointments").eq("salon_id", salon_id).execute()
        count = len([a for a in appointments["data"] if a["status"] == "confirmed"])
        return f"Today's stats: {count} bookings"

    if command == "TOMORROW":
        return "Tomorrow: 3 appointments at 10am, 2pm, 4pm"

    if command == "UNPAID":
        invoices = db.table("invoices").eq("salon_id", salon_id).execute()
        unpaid = [inv for inv in invoices["data"] if inv["payment_status"] == "unpaid"]
        total = sum(inv["amount"] for inv in unpaid)
        return f"Unpaid invoices: {len(unpaid)} customers, ₹{total/100}"

    return "Commands: STATS, TOMORROW, UNPAID"


def handle_customer_flow(phone: str, message: str):
    """Handle multi-step customer booking flow."""
    db = get_db()
    session = Session(phone)
    state = session.get()

    if not state:
        session.set(
            {
                "step": "start",
                "phone": phone,
                "created_at": datetime.now().isoformat(),
            }
        )
        return show_salons_menu()

    step = state.get("step")

    if step == "start":
        if message.strip() == "1":
            session.update(
                {
                    "step": "salon_selected",
                    "salon_id": "dd4ccd26-3d0d-4c27-8f69-89b5928581b8",
                }
            )
            return show_services_menu("dd4ccd26-3d0d-4c27-8f69-89b5928581b8")
        return "Reply with 1"

    if step == "salon_selected":
        salon_id = state.get("salon_id")
        if message.strip() == "1":
            services = db.table("services").eq("salon_id", salon_id).execute()
            if services["data"]:
                service_id = services["data"][0]["id"]
                session.update(
                    {"step": "service_selected", "service_id": service_id}
                )
                return show_services_menu(salon_id)
            return "No services available"
        return "Reply with 1"

    if step == "service_selected":
        salon_id = state.get("salon_id")
        if message.strip() == "1":
            staff = db.table("staff").eq("salon_id", salon_id).execute()
            if staff["data"]:
                staff_id = staff["data"][0]["id"]
                session.update(
                    {"step": "staff_selected", "staff_id": staff_id}
                )
                return show_staff_menu(salon_id)
            return "No staff available"
        return "Reply with 1"

    if step == "staff_selected":
        if message.strip() in ["1", "2", "3", "4"]:
            times = ["14:00", "15:00", "16:00", "17:00"]
            time_idx = int(message.strip()) - 1
            selected_time = times[time_idx]
            session.update(
                {"step": "time_selected", "appointment_time": selected_time}
            )
            return confirm_booking(session.get())
        return "Reply with 1-4"

    if step == "time_selected":
        if message.upper().strip() == "CONFIRM":
            booking_data = session.get()
            create_appointment(db, phone, booking_data)
            session.delete()
            return "✓ Appointment confirmed!"
        return "Reply CONFIRM to book"

    return "Invalid state"

def show_salons_menu():
    return """Welcome to Ping!

Choose a salon:
1. Neha's Beauty Salon

Reply with number"""


def show_services_menu(salon_id: str):
    db = get_db()
    services = db.table("services").eq("salon_id", salon_id).execute()

    if not services["data"]:
        return "No services available"

    menu = "Choose a service:\n"
    for i, service in enumerate(services["data"], 1):
        price = service["price"] / 100
        menu += f"{i}. {service['service_name']} - ₹{price}\n"
    menu += "\nReply with number"
    return menu


def show_staff_menu(salon_id: str):
    db = get_db()
    staff = db.table("staff").eq("salon_id", salon_id).execute()

    if not staff["data"]:
        return "No staff available"

    menu = "Choose a stylist:\n"
    for i, s in enumerate(staff["data"], 1):
        menu += f"{i}. {s['staff_name']}\n"
    menu += "\nReply with number"
    return menu


def show_time_menu():
    times = ["2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM"]
    menu = "Choose a time:\n"
    for i, time in enumerate(times, 1):
        menu += f"{i}. {time}\n"
    menu += "\nReply with number"
    return menu


def confirm_booking(booking_data: dict):
    db = get_db()
    salon_id = booking_data.get("salon_id")
    service_id = booking_data.get("service_id")
    staff_id = booking_data.get("staff_id")
    appointment_time = booking_data.get("appointment_time")
    
    # Get service name
    service = db.table("services").eq("id", service_id).execute()
    service_name = service["data"][0]["service_name"] if service["data"] else "Unknown"
    
    # Get staff name
    staff = db.table("staff").eq("id", staff_id).execute()
    staff_name = staff["data"][0]["staff_name"] if staff["data"] else "Unknown"
    
    return f"""Confirm your booking?

Service: {service_name}
Stylist: {staff_name}
Time: {appointment_time}

Reply CONFIRM"""


def create_appointment(db, phone: str, booking_data: dict):
    """Create appointment in database."""
    salon_id = booking_data.get("salon_id")

    customer_response = db.table("customers").eq("salon_id", salon_id).execute()
    customer_id = None

    for cust in customer_response["data"]:
        if cust["phone"] == phone:
            customer_id = cust["id"]
            break

    if not customer_id:
        cust_response = db.table("customers").insert(
            {
                "salon_id": salon_id,
                "phone": phone,
                "customer_name": "Customer",
                "opted_out_broadcasts": False,
            }
        )
        customer_id = cust_response["data"][0]["id"]

    db.table("appointments").insert(
        {
            "salon_id": salon_id,
            "customer_id": customer_id,
            "staff_id": booking_data.get("staff_id"),
            "service_id": booking_data.get("service_id"),
            "appointment_date": "2026-05-20",
            "appointment_time": booking_data.get("appointment_time"),
            "status": "confirmed",
        }
    )


def send_whatsapp_response(to_number: str, message: str):
    """Send WhatsApp message via Twilio."""
    from twilio.rest import Client
    import os

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_number = os.getenv("TWILIO_WHATSAPP_NUMBER")

    client = Client(account_sid, auth_token)

    try:
        client.messages.create(
            body=message,
            from_=twilio_number,
            to=to_number,
        )
    except Exception as e:
        print(f"Error sending: {e}")