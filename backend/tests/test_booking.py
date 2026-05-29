from datetime import datetime, timedelta

import pytest

from config import IST
from services import booking
from services.booking import BookingError
from tests.fakes import FakeDB


SALON = "salon-1"
STAFF = "staff-1"
SERVICE = "service-1"


def _tomorrow():
    return (datetime.now(IST) + timedelta(days=1)).date()


def _seed():
    db = FakeDB()
    db.table("services").insert(
        {"id": SERVICE, "salon_id": SALON, "service_name": "Haircut", "price": 40000, "duration_minutes": 60, "is_active": True}
    )
    db.table("staff").insert({"id": STAFF, "salon_id": SALON, "staff_name": "Rakesh", "is_active": True})
    return db


def test_parse_helpers():
    assert booking.parse_time("14:00").hour == 14
    assert booking.parse_time("14:00:00").minute == 0
    assert booking.parse_date("2026-05-30").day == 30


def test_available_slots_excludes_conflicts():
    db = _seed()
    day = _tomorrow()
    # Book 11:00-12:00 for the staff member.
    db.table("appointments").insert(
        {
            "id": "a1",
            "salon_id": SALON,
            "staff_id": STAFF,
            "service_id": SERVICE,
            "appointment_date": str(day),
            "appointment_time": "11:00",
            "status": "confirmed",
        }
    )
    slots = booking.available_slots(db, SALON, STAFF, day, duration=60)
    labels = [s.strftime("%H:%M") for s in slots]
    assert "11:00" not in labels
    assert "11:30" not in labels  # would overlap the 11:00-12:00 booking
    assert "10:00" in labels
    assert "12:00" in labels


def test_has_conflict():
    db = _seed()
    day = _tomorrow()
    db.table("appointments").insert(
        {
            "id": "a1",
            "salon_id": SALON,
            "staff_id": STAFF,
            "service_id": SERVICE,
            "appointment_date": str(day),
            "appointment_time": "14:00",
            "status": "confirmed",
        }
    )
    assert booking.has_conflict(db, SALON, STAFF, day, booking.parse_time("14:30"), 60) is True
    assert booking.has_conflict(db, SALON, STAFF, day, booking.parse_time("16:00"), 60) is False


def test_create_appointment_rejects_double_booking():
    db = _seed()
    day = _tomorrow()
    service = {"id": SERVICE, "duration_minutes": 60}
    booking.create_appointment(
        db, SALON, "cust-1", STAFF, service, day, booking.parse_time("15:00"), validate_hours=False
    )
    with pytest.raises(BookingError):
        booking.create_appointment(
            db, SALON, "cust-2", STAFF, service, day, booking.parse_time("15:30"), validate_hours=False
        )


def test_get_or_create_customer_is_idempotent():
    db = _seed()
    c1 = booking.get_or_create_customer(db, SALON, "9999999999", "Asha")
    c2 = booking.get_or_create_customer(db, SALON, "9999999999", "Asha")
    assert c1["id"] == c2["id"]
    assert len(db.store["customers"]) == 1
