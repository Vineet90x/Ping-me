from fastapi import APIRouter, HTTPException

from models.appointment import AppointmentCreate, AppointmentResponse, RescheduleRequest
from services import booking
from services.booking import BookingError
from services.database import get_db

router = APIRouter()

VALID_STATUSES = ("confirmed", "completed", "cancelled", "no_show")


def _require_salon(db, salon_id: str) -> dict:
    resp = db.table("salons").eq("id", salon_id).execute()
    if not resp["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    return resp["data"][0]


@router.post("/{salon_id}/appointments", response_model=AppointmentResponse)
def create_appointment(salon_id: str, appointment: AppointmentCreate):
    db = get_db()
    _require_salon(db, salon_id)

    # Service and staff must belong to THIS salon.
    service_resp = (
        db.table("services").eq("id", appointment.service_id).eq("salon_id", salon_id).execute()
    )
    if not service_resp["data"]:
        raise HTTPException(status_code=404, detail="Service not found")
    service = service_resp["data"][0]

    staff_resp = (
        db.table("staff").eq("id", appointment.staff_id).eq("salon_id", salon_id).execute()
    )
    if not staff_resp["data"]:
        raise HTTPException(status_code=404, detail="Staff not found")

    try:
        customer = booking.get_or_create_customer(
            db, salon_id, appointment.customer_phone, appointment.customer_name
        )
        created = booking.create_appointment(
            db,
            salon_id=salon_id,
            customer_id=customer["id"],
            staff_id=appointment.staff_id,
            service=service,
            appt_date=appointment.appointment_date,
            appt_time=appointment.appointment_time,
        )
    except BookingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return created


@router.get("/{salon_id}/appointments")
def list_appointments(salon_id: str, date: str | None = None, status: str | None = None):
    db = get_db()
    _require_salon(db, salon_id)

    query = db.table("appointments").eq("salon_id", salon_id)
    if date:
        query = query.eq("appointment_date", date)
    if status:
        query = query.eq("status", status)
    resp = query.order("appointment_date").order("appointment_time").execute()
    return resp["data"]


@router.get("/{salon_id}/appointments/{appointment_id}")
def get_appointment(salon_id: str, appointment_id: str):
    db = get_db()
    resp = db.table("appointments").eq("id", appointment_id).eq("salon_id", salon_id).execute()
    if not resp["data"]:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return resp["data"][0]


@router.patch("/{salon_id}/appointments/{appointment_id}")
def update_appointment(salon_id: str, appointment_id: str, status: str):
    db = get_db()
    if status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"Invalid status. Use one of: {', '.join(VALID_STATUSES)}"
        )

    resp = db.table("appointments").eq("id", appointment_id).eq("salon_id", salon_id).execute()
    if not resp["data"]:
        raise HTTPException(status_code=404, detail="Appointment not found")

    db.table("appointments").eq("id", appointment_id).update({"status": status})
    return {"message": "Appointment updated", "status": status}


@router.post("/{salon_id}/appointments/{appointment_id}/reschedule")
def reschedule_appointment(salon_id: str, appointment_id: str, body: RescheduleRequest):
    db = get_db()
    resp = db.table("appointments").eq("id", appointment_id).eq("salon_id", salon_id).execute()
    if not resp["data"]:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appt = resp["data"][0]

    service_resp = db.table("services").eq("id", appt["service_id"]).execute()
    service = service_resp["data"][0] if service_resp["data"] else {"id": appt["service_id"]}

    try:
        booking.validate_booking_time(
            body.new_date, body.new_time, service, booking.get_settings(db, salon_id)
        )
        duration = service.get("duration_minutes", booking.SLOT_STEP_MINUTES)
        # Ignore the appointment's own current slot when checking conflicts.
        if booking.has_conflict(db, salon_id, appt["staff_id"], body.new_date, body.new_time, duration):
            raise BookingError("That slot is already booked. Please pick another time.")
    except BookingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    db.table("appointments").eq("id", appointment_id).update(
        {
            "appointment_date": str(body.new_date),
            "appointment_time": str(body.new_time),
            "status": "confirmed",
        }
    )
    return {"message": "Appointment rescheduled", "date": str(body.new_date), "time": str(body.new_time)}
