"""Tests for the UX fixes: any-staff slots, chairs cap, reordered booking flow,
HI-at-confirm, and the unpaid-invoice nudge. All against in-memory fakes."""
from datetime import datetime, timedelta

import pytest

from config import IST
from routes import webhook
from services import booking
from tests.fakes import FakeDB, FakeSession


SALON = "salon-1"
SERVICE = "service-1"


def _tomorrow():
    return (datetime.now(IST) + timedelta(days=1)).date()


def _seed(num_staff=2, max_concurrent=None):
    db = FakeDB()
    db.table("salons").insert(
        {"id": SALON, "owner_phone": "9000000000", "owner_name": "N", "salon_name": "Neha Salon", "upi_id": "n@ok"}
    )
    db.table("services").insert(
        {"id": SERVICE, "salon_id": SALON, "service_name": "Haircut", "price": 40000, "duration_minutes": 60, "is_active": True}
    )
    for i in range(num_staff):
        db.table("staff").insert({"id": f"staff-{i+1}", "salon_id": SALON, "staff_name": f"S{i+1}", "is_active": True})
    settings = {"salon_id": SALON, "opening_time": "10:00", "closing_time": "20:00",
                "days_advance_booking": 30, "min_advance_booking_minutes": 60}
    if max_concurrent is not None:
        settings["max_concurrent"] = max_concurrent
    db.table("settings").insert(settings)
    return db


# --------------------------------------------------------------------------- #
# Chairs / max_concurrent
# --------------------------------------------------------------------------- #
def test_max_concurrent_defaults_to_staff_count():
    assert booking.get_max_concurrent({}, staff_count=3) == 3
    assert booking.get_max_concurrent({"max_concurrent": None}, 3) == 3
    assert booking.get_max_concurrent({"max_concurrent": 2}, 3) == 2


def test_two_chairs_block_third_concurrent_booking():
    # 3 stylists but only 2 chairs.
    db = _seed(num_staff=3, max_concurrent=2)
    day = _tomorrow()
    svc = {"id": SERVICE, "duration_minutes": 60}
    booking.create_appointment(db, SALON, "c1", "staff-1", svc, day, booking.parse_time("15:00"), validate_hours=False)
    booking.create_appointment(db, SALON, "c2", "staff-2", svc, day, booking.parse_time("15:00"), validate_hours=False)
    # Third stylist is free, but both chairs are taken at 15:00.
    with pytest.raises(booking.BookingError):
        booking.create_appointment(db, SALON, "c3", "staff-3", svc, day, booking.parse_time("15:00"), validate_hours=False)


def test_any_staff_slots_and_free_staff_at():
    db = _seed(num_staff=2)
    day = _tomorrow()
    svc = {"id": SERVICE, "duration_minutes": 60}
    # Book staff-1 at 11:00; staff-2 still free, so 11:00 should still be offered.
    booking.create_appointment(db, SALON, "c1", "staff-1", svc, day, booking.parse_time("11:00"), validate_hours=False)
    slots = [s.strftime("%H:%M") for s in booking.available_slots_any_staff(db, SALON, day, 60)]
    assert "11:00" in slots  # staff-2 covers it
    free = booking.free_staff_at(db, SALON, day, booking.parse_time("11:00"), 60)
    free_ids = {s["id"] for s in free}
    assert free_ids == {"staff-2"}  # only staff-2 is free at 11:00


# --------------------------------------------------------------------------- #
# Reordered booking flow: service -> date -> time -> staff
# --------------------------------------------------------------------------- #
def test_booking_flow_order_service_date_time_staff():
    db = _seed(num_staff=2)
    session = FakeSession()
    # Start (single salon auto-selected).
    webhook._start(db, session, "9870001111")
    assert session.get()["step"] == "choose_service"

    out = webhook._step_service(db, session, session.get(), "9870001111", "1")
    assert session.get()["step"] == "choose_date"  # day comes right after service
    assert "day" in out.lower()

    out = webhook._step_date(db, session, session.get(), "9870001111", "1")  # today (may have slots)
    # If today has no slots (late in the day) pick tomorrow.
    if session.get()["step"] != "choose_time":
        out = webhook._step_date(db, session, session.get(), "9870001111", "2")
    assert session.get()["step"] == "choose_time"

    out = webhook._step_time(db, session, session.get(), "9870001111", "1")
    assert session.get()["step"] == "choose_staff"
    assert "stylist" in out.lower() and "Any available" in out

    out = webhook._step_staff(db, session, session.get(), "9870001111", "0")  # any available
    assert session.get()["step"] in ("ask_name", "confirm")
    assert session.get().get("staff_id") in ("staff-1", "staff-2")


# --------------------------------------------------------------------------- #
# HI at the confirm step must NOT restart
# --------------------------------------------------------------------------- #
class _MemSession:
    """A by-phone in-memory Session, to patch webhook.Session in tests."""

    _store: dict = {}

    def __init__(self, phone):
        self.phone = phone

    def get(self):
        return self._store.get(self.phone)

    def set(self, data, ttl=None):
        self._store[self.phone] = dict(data)

    def update(self, data):
        cur = self._store.get(self.phone) or {}
        cur.update(data)
        self._store[self.phone] = cur

    def delete(self):
        self._store.pop(self.phone, None)


def test_hi_at_confirm_reprompts_not_restart(monkeypatch):
    db = _seed(num_staff=1)
    monkeypatch.setattr(webhook, "Session", _MemSession)
    _MemSession._store.clear()
    phone = "9870002222"
    _MemSession(phone).set(
        {
            "step": "confirm",
            "salon_id": SALON,
            "salon_name": "Neha Salon",
            "service_id": SERVICE,
            "service_meta": {SERVICE: {"name": "Haircut", "price": 40000, "duration": 60}},
            "staff_id": "staff-1",
            "staff_names": {"staff-1": "S1"},
            "appt_date": str(_tomorrow()),
            "appt_time": "15:00",
            "customer_name": "Asha",
        }
    )
    # At the confirm step, "HI" should re-show the summary, not reset the booking.
    out = webhook.handle_customer_flow(db, phone, "HI")
    assert "CONFIRM" in out.upper()
    assert _MemSession._store[phone]["step"] == "confirm"  # still on confirm, not wiped


# --------------------------------------------------------------------------- #
# Unpaid-invoice nudge
# --------------------------------------------------------------------------- #
def test_notify_unpaid_invoices(monkeypatch):
    import tasks

    db = _seed()
    db.table("customers").insert({"id": "cust-1", "salon_id": SALON, "phone": "9870003333", "customer_name": "Asha"})
    old = (datetime.now(IST).replace(tzinfo=None) - timedelta(days=2)).isoformat()
    recent = datetime.now(IST).replace(tzinfo=None).isoformat()
    db.table("invoices").insert({"salon_id": SALON, "customer_id": "cust-1", "amount": 40000,
                                 "payment_status": "unpaid", "created_at": old})
    db.table("invoices").insert({"salon_id": SALON, "customer_id": "cust-1", "amount": 10000,
                                 "payment_status": "unpaid", "created_at": recent})  # too new, excluded

    sent = []
    monkeypatch.setattr(tasks, "get_db", lambda: db)
    monkeypatch.setattr(tasks, "send_whatsapp", lambda to, body, **k: sent.append((to, body)) or True)

    result = tasks.notify_unpaid_invoices()
    assert result["notified"] == 1
    assert sent and sent[0][0] == "+919000000000"
    assert "1 invoice" in sent[0][1]  # only the >24h-old one counted
