from fastapi import APIRouter, HTTPException
from models.appointment import AppointmentCreate, AppointmentResponse
from services.database import get_db
from datetime import datetime, timedelta,timezone

router = APIRouter()

@router.post("/{salon_id}/appointments", response_model=AppointmentResponse)
def create_appointment(salon_id: str, appointment: AppointmentCreate):
    db = get_db()
    
    # Check salon exists
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    
    salon = salon_response["data"][0]
    settings_response = db.table("settings").eq("salon_id", salon_id).execute()
    settings = settings_response["data"][0] if settings_response["data"] else None
    
     # Get salon settings
    settings_response = db.table("settings").eq("salon_id", salon_id).execute()
    if settings_response["data"]:
        settings = settings_response["data"][0]
        opening_time = settings["opening_time"]
        closing_time = settings["closing_time"]
    else:
        opening_time = "10:00"
        closing_time = "20:00"
    
    # Validate appointment time is within business hours
    appointment_time_str = str(appointment.appointment_time)
    if appointment_time_str < opening_time or appointment_time_str >= closing_time:
        raise HTTPException(
            status_code=400, 
            detail=f"Appointment must be between {opening_time} and {closing_time}"
        )
        
    # Check minimum advance booking time

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    appointment_datetime = datetime.combine(appointment.appointment_date, appointment.appointment_time)
    min_advance = settings["min_advance_booking_minutes"] if settings else 60
    
    if appointment_datetime < now + timedelta(minutes=min_advance):
        raise HTTPException(status_code=400, detail=f"Must book at least {min_advance} minutes in advance")
    
    # Check service exists
    service_response = db.table("services").eq("id", appointment.service_id).execute()
    if not service_response["data"]:
        raise HTTPException(status_code=404, detail="Service not found")
    
    service = service_response["data"][0]
    
    # Check staff exists
    staff_response = db.table("staff").eq("id", appointment.staff_id).execute()
    if not staff_response["data"]:
        raise HTTPException(status_code=404, detail="Staff not found")
    
    # Check slot availability (no overlapping appointments)
    existing = db.table("appointments").eq("staff_id", appointment.staff_id).execute()
    appointment_end = datetime.combine(
        appointment.appointment_date,
        datetime.combine(datetime.min.date(), appointment.appointment_time).time()
    ) + timedelta(minutes=service["duration_minutes"])
    
    for apt in existing["data"]:
        if apt["status"] in ["confirmed", "completed"]:
            apt_start = datetime.fromisoformat(str(apt["appointment_date"]) + " " + str(apt["appointment_time"]))
            apt_end = apt_start + timedelta(minutes=service["duration_minutes"])
            
            apt_datetime = datetime.combine(appointment.appointment_date, appointment.appointment_time)
            if apt_datetime < apt_end and appointment_end > apt_start:
                raise HTTPException(status_code=400, detail="Slot already booked")
    
    # Get or create customer
    customer_response = db.table("customers").eq("salon_id", salon_id).execute()
    customer_data = None
    
    if customer_response["data"]:
        for cust in customer_response["data"]:
            if cust["phone"] == appointment.customer_phone:
                customer_data = cust
                break
    
    if not customer_data:
        # Create new customer
        cust_response = db.table("customers").insert({
            "salon_id": salon_id,
            "phone": appointment.customer_phone,
            "customer_name": appointment.customer_name,
            "opted_out_broadcasts": False
        })
        if cust_response["data"]:
            customer_data = cust_response["data"][0]
        else:
            raise HTTPException(status_code=400, detail="Failed to create customer")
    
    # Create appointment
    response = db.table("appointments").insert({
        "salon_id": salon_id,
        "customer_id": customer_data["id"],
        "staff_id": appointment.staff_id,
        "service_id": appointment.service_id,
        "appointment_date": str(appointment.appointment_date),
        "appointment_time": str(appointment.appointment_time),
        "status": "confirmed"
    })
    
    if not response["data"]:
        raise HTTPException(status_code=400, detail="Insert failed")
    
    return response["data"][0]

@router.get("/{salon_id}/appointments")
def list_appointments(salon_id: str, date: str = None):
    db = get_db()
    
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    
    response = db.table("appointments").eq("salon_id", salon_id).execute()
    appointments = response["data"] if response["data"] else []
    
    if date:
        appointments = [apt for apt in appointments if apt["appointment_date"] == date]
    
    return appointments

@router.get("/{salon_id}/appointments/{appointment_id}")
def get_appointment(salon_id: str, appointment_id: str):
    db = get_db()
    
    response = db.table("appointments").eq("id", appointment_id).execute()
    if not response["data"]:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    return response["data"][0]

@router.patch("/{salon_id}/appointments/{appointment_id}")
def update_appointment(salon_id: str, appointment_id: str, status: str):
    db = get_db()
    
    if status not in ["confirmed", "completed", "cancelled", "no_show"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    response = db.table("appointments").eq("id", appointment_id).execute()
    if not response["data"]:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    db.table("appointments").eq("id", appointment_id).update({"status": status})
    
    return {"message": "Appointment updated", "status": status}

@router.post("/{salon_id}/appointments/{appointment_id}/reschedule")
def reschedule_appointment(salon_id: str, appointment_id: str, new_date: str, new_time: str):
    db = get_db()
    
    response = db.table("appointments").eq("id", appointment_id).execute()
    if not response["data"]:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    db.table("appointments").eq("id", appointment_id).update({
        "appointment_date": new_date,
        "appointment_time": new_time
    })
    
    return {"message": "Appointment rescheduled"}