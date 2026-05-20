from fastapi import APIRouter, HTTPException, Request
from services.database import get_db
import json

router = APIRouter()

@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Receive WhatsApp messages from Twilio
    """
    try:
        body = await request.form()
        
        # Parse Twilio webhook
        from_number = body.get("From")
        message_body = body.get("Body")
        
        print(f"DEBUG: Raw body = {dict(body)}")
        print(f"DEBUG: From = {from_number}")
        print(f"DEBUG: Body = {message_body}")
        
        if not from_number or not message_body:
            return {"status": "error", "detail": "Missing From or Body"}
        
        # Extract phone without 'whatsapp:' prefix
        customer_phone = from_number.replace("whatsapp:", "").replace("+91", "").replace("+1", "")
        
        print(f"DEBUG: Customer phone = {customer_phone}")
        
        # Route message
        response = route_message(customer_phone, message_body)
        
        # Send response back via Twilio
        send_whatsapp_response(from_number, response)
        
        return {"status": "ok"}
    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "detail": str(e)}

def route_message(phone: str, message: str):
    """
    Determine if sender is owner or customer
    """
    db = get_db()
    
    # Check if phone is a salon owner
    salon_response = db.table("salons").eq("owner_phone", phone).execute()
    
    if salon_response["data"]:
        # Owner command
        return handle_owner_command(salon_response["data"][0], message)
    else:
        # Customer booking
        return handle_customer_booking(phone, message)

def handle_owner_command(salon: dict, command: str):
    """
    Handle owner commands: STATS, TOMORROW, UNPAID, etc.
    """
    command = command.upper().strip()
    
    if command == "STATS":
        return f"Today's stats: 5 bookings, ₹2,500 earned"
    elif command == "TOMORROW":
        return "Tomorrow: 3 appointments at 10am, 2pm, 4pm"
    elif command == "UNPAID":
        return "Unpaid invoices: 2 customers, ₹1,200 total"
    else:
        return "Commands: STATS, TOMORROW, UNPAID, SCHEDULE"

def handle_customer_booking(phone: str, message: str):
    """
    Handle customer booking flow
    """
    return """Welcome to Ping!

Choose a service:
1. Haircut
2. Spa
3. Color

Reply with number"""

def send_whatsapp_response(to_number: str, message: str):
    """
    Send WhatsApp message via Twilio
    """
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
            to=to_number
        )
        print(f"Sent to {to_number}")
    except Exception as e:
        print(f"Error sending: {e}")