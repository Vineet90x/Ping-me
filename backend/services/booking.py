"""Shared appointment-booking logic.

Used by both the REST API (`routes/appointments.py`) and the WhatsApp webhook
so they validate business hours, advance-booking rules and slot conflicts
identically.
"""
from datetime import date, datetime, time, timedelta

from config import (
    DEFAULT_CLOSING_TIME,
    DEFAULT_DAYS_ADVANCE,
    DEFAULT_MIN_ADVANCE_MINUTES,
    DEFAULT_OPENING_TIME,
    now_ist,
)
from services.database import DB

ACTIVE_STATUSES = ("confirmed", "completed")
SLOT_STEP_MINUTES = 30


class BookingError(Exception):
    """A booking could not be made for a business-rule reason (not a server error)."""


def parse_time(value) -> time:
    """Accept a ``time``, ``"HH:MM"`` or ``"HH:MM:SS"`` and return a ``time``."""
    if isinstance(value, time):
        return value
    text = str(value).strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise BookingError(f"Invalid time: {value!r}")


def parse_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise BookingError(f"Invalid date: {value!r}") from exc


def get_settings(db: DB, salon_id: str) -> dict:
    """Return effective settings for a salon, filling in defaults."""
    resp = db.table("settings").eq("salon_id", salon_id).execute()
    row = resp["data"][0] if resp["data"] else {}
    return {
        "opening_time": str(row.get("opening_time") or DEFAULT_OPENING_TIME)[:5],
        "closing_time": str(row.get("closing_time") or DEFAULT_CLOSING_TIME)[:5],
        "days_advance_booking": row.get("days_advance_booking") or DEFAULT_DAYS_ADVANCE,
        "min_advance_booking_minutes": (
            row.get("min_advance_booking_minutes")
            if row.get("min_advance_booking_minutes") is not None
            else DEFAULT_MIN_ADVANCE_MINUTES
        ),
        # Physical capacity (chairs). None -> "no extra limit beyond staff count".
        "max_concurrent": row.get("max_concurrent"),
    }


def get_max_concurrent(settings: dict, staff_count: int) -> int:
    """Effective simultaneous-appointment cap (the salon's chairs).

    If unset, the cap is just the number of stylists (each works one client).
    A salon with more stylists than chairs sets ``max_concurrent`` to the
    chair count to stop overbooking the room.
    """
    value = settings.get("max_concurrent")
    if not value or value <= 0:
        return max(staff_count, 1)
    return value


def get_active_services(db: DB, salon_id: str) -> list[dict]:
    resp = db.table("services").eq("salon_id", salon_id).eq("is_active", "true").order("price").execute()
    return resp["data"]


def get_active_staff(db: DB, salon_id: str) -> list[dict]:
    resp = db.table("staff").eq("salon_id", salon_id).eq("is_active", "true").order("staff_name").execute()
    return resp["data"]


def _service_duration_map(db: DB, salon_id: str) -> dict[str, int]:
    # Include inactive services: an appointment may reference a since-removed one.
    resp = db.table("services").eq("salon_id", salon_id).execute()
    return {s["id"]: s.get("duration_minutes", SLOT_STEP_MINUTES) for s in resp["data"]}


def _busy_intervals(db: DB, salon_id: str, staff_id: str, appt_date: date) -> list[tuple]:
    resp = (
        db.table("appointments")
        .eq("salon_id", salon_id)
        .eq("staff_id", staff_id)
        .eq("appointment_date", str(appt_date))
        .execute()
    )
    durations = _service_duration_map(db, salon_id)
    intervals = []
    for apt in resp["data"]:
        if apt.get("status") not in ACTIVE_STATUSES:
            continue
        start = datetime.combine(parse_date(apt["appointment_date"]), parse_time(apt["appointment_time"]))
        dur = durations.get(apt.get("service_id"), SLOT_STEP_MINUTES)
        intervals.append((start, start + timedelta(minutes=dur)))
    return intervals


def _overlaps(start: datetime, end: datetime, intervals: list[tuple]) -> bool:
    return any(start < busy_end and end > busy_start for busy_start, busy_end in intervals)


def has_conflict(db: DB, salon_id: str, staff_id: str, appt_date: date, appt_time: time, duration: int) -> bool:
    start = datetime.combine(appt_date, appt_time)
    end = start + timedelta(minutes=duration)
    return _overlaps(start, end, _busy_intervals(db, salon_id, staff_id, appt_date))


def _salon_intervals(db: DB, salon_id: str, appt_date: date) -> list[tuple]:
    """Every active appointment for the salon that day, as (staff_id, start, end)."""
    resp = (
        db.table("appointments")
        .eq("salon_id", salon_id)
        .eq("appointment_date", str(appt_date))
        .execute()
    )
    durations = _service_duration_map(db, salon_id)
    out = []
    for apt in resp["data"]:
        if apt.get("status") not in ACTIVE_STATUSES:
            continue
        start = datetime.combine(parse_date(apt["appointment_date"]), parse_time(apt["appointment_time"]))
        dur = durations.get(apt.get("service_id"), SLOT_STEP_MINUTES)
        out.append((apt.get("staff_id"), start, start + timedelta(minutes=dur)))
    return out


def _concurrent(intervals: list[tuple], start: datetime, end: datetime) -> int:
    return sum(1 for (_sid, s, e) in intervals if start < e and end > s)


def _staff_free(intervals: list[tuple], staff_id: str, start: datetime, end: datetime) -> bool:
    return not any(sid == staff_id and start < e and end > s for (sid, s, e) in intervals)


def available_slots_any_staff(
    db: DB,
    salon_id: str,
    appt_date: date,
    duration: int,
    settings: dict | None = None,
    max_slots: int = 8,
) -> list[time]:
    """Start-times the salon can take, given chairs + at least one free stylist.

    Used by the WhatsApp flow so the customer picks a TIME first (across all
    stylists), then a stylist — instead of hitting a dead-end per stylist.
    """
    settings = settings or get_settings(db, salon_id)
    staff = get_active_staff(db, salon_id)
    if not staff:
        return []
    max_concurrent = get_max_concurrent(settings, len(staff))
    open_t = parse_time(settings["opening_time"])
    close_t = parse_time(settings["closing_time"])
    earliest = now_ist() + timedelta(minutes=settings["min_advance_booking_minutes"])

    intervals = _salon_intervals(db, salon_id, appt_date)
    day_end = datetime.combine(appt_date, close_t)
    cursor = datetime.combine(appt_date, open_t)

    slots: list[time] = []
    while cursor + timedelta(minutes=duration) <= day_end and len(slots) < max_slots:
        slot_end = cursor + timedelta(minutes=duration)
        if cursor >= earliest and _concurrent(intervals, cursor, slot_end) < max_concurrent:
            if any(_staff_free(intervals, s["id"], cursor, slot_end) for s in staff):
                slots.append(cursor.time())
        cursor += timedelta(minutes=SLOT_STEP_MINUTES)
    return slots


def free_staff_at(
    db: DB,
    salon_id: str,
    appt_date: date,
    appt_time: time,
    duration: int,
    settings: dict | None = None,
) -> list[dict]:
    """Active stylists with no clash at this time (empty if chairs are full)."""
    settings = settings or get_settings(db, salon_id)
    staff = get_active_staff(db, salon_id)
    max_concurrent = get_max_concurrent(settings, len(staff))
    intervals = _salon_intervals(db, salon_id, appt_date)
    start = datetime.combine(appt_date, appt_time)
    end = start + timedelta(minutes=duration)
    if _concurrent(intervals, start, end) >= max_concurrent:
        return []
    return [s for s in staff if _staff_free(intervals, s["id"], start, end)]


def available_slots(
    db: DB,
    salon_id: str,
    staff_id: str,
    appt_date: date,
    duration: int,
    settings: dict | None = None,
    max_slots: int = 8,
) -> list[time]:
    """Free start-times for a staff member on a date, honouring hours + advance rules."""
    settings = settings or get_settings(db, salon_id)
    open_t = parse_time(settings["opening_time"])
    close_t = parse_time(settings["closing_time"])
    min_advance = settings["min_advance_booking_minutes"]
    earliest = now_ist() + timedelta(minutes=min_advance)

    intervals = _busy_intervals(db, salon_id, staff_id, appt_date)
    day_end = datetime.combine(appt_date, close_t)
    cursor = datetime.combine(appt_date, open_t)

    slots: list[time] = []
    while cursor + timedelta(minutes=duration) <= day_end and len(slots) < max_slots:
        slot_end = cursor + timedelta(minutes=duration)
        if cursor >= earliest and not _overlaps(cursor, slot_end, intervals):
            slots.append(cursor.time())
        cursor += timedelta(minutes=SLOT_STEP_MINUTES)
    return slots


def get_or_create_customer(db: DB, salon_id: str, phone: str, name: str = "Customer") -> dict:
    # Fast path: return the existing customer without touching their name.
    resp = db.table("customers").eq("salon_id", salon_id).eq("phone", phone).execute()
    if resp["data"]:
        return resp["data"][0]

    # Race-safe create: relies on the UNIQUE (salon_id, phone) constraint. If a
    # concurrent request just created this customer, the upsert ignores the
    # conflict (returns nothing) and we re-fetch the winning row instead of
    # raising on a duplicate-key error or creating a second row.
    created = db.table("customers").upsert(
        {
            "salon_id": salon_id,
            "phone": phone,
            "customer_name": name,
            "opted_out_broadcasts": False,
        },
        on_conflict="salon_id,phone",
        ignore_duplicates=True,
    )
    if created["data"]:
        return created["data"][0]

    resp = db.table("customers").eq("salon_id", salon_id).eq("phone", phone).execute()
    if resp["data"]:
        return resp["data"][0]
    raise BookingError("Could not create customer record")


def validate_booking_time(appt_date: date, appt_time: time, service: dict, settings: dict) -> None:
    """Raise BookingError if the requested time breaks any business rule."""
    open_t = parse_time(settings["opening_time"])
    close_t = parse_time(settings["closing_time"])
    duration = service.get("duration_minutes", SLOT_STEP_MINUTES)

    start = datetime.combine(appt_date, appt_time)
    end = start + timedelta(minutes=duration)

    if appt_time < open_t:
        raise BookingError(f"We open at {settings['opening_time']}.")
    if end.time() > close_t:
        raise BookingError(f"That would run past closing ({settings['closing_time']}).")

    earliest = now_ist() + timedelta(minutes=settings["min_advance_booking_minutes"])
    if start < earliest:
        raise BookingError(
            f"Please book at least {settings['min_advance_booking_minutes']} minutes in advance."
        )


def create_appointment(
    db: DB,
    salon_id: str,
    customer_id: str,
    staff_id: str,
    service: dict,
    appt_date: date,
    appt_time: time,
    validate_hours: bool = True,
    settings: dict | None = None,
) -> dict:
    """Create an appointment after re-checking the slot is still free.

    Raises ``BookingError`` on any business-rule violation.
    """
    settings = settings or get_settings(db, salon_id)
    if validate_hours:
        validate_booking_time(appt_date, appt_time, service, settings)

    duration = service.get("duration_minutes", SLOT_STEP_MINUTES)
    if has_conflict(db, salon_id, staff_id, appt_date, appt_time, duration):
        raise BookingError("That slot was just taken. Please pick another time.")

    # Capacity (chairs): even if this stylist is free, the room may be full.
    staff_count = len(get_active_staff(db, salon_id))
    max_concurrent = get_max_concurrent(settings, staff_count)
    start = datetime.combine(appt_date, appt_time)
    end = start + timedelta(minutes=duration)
    if _concurrent(_salon_intervals(db, salon_id, appt_date), start, end) >= max_concurrent:
        raise BookingError("All chairs are booked at that time. Please pick another slot.")

    resp = db.table("appointments").insert(
        {
            "salon_id": salon_id,
            "customer_id": customer_id,
            "staff_id": staff_id,
            "service_id": service["id"],
            "appointment_date": str(appt_date),
            "appointment_time": str(appt_time),
            "status": "confirmed",
        }
    )
    if not resp["data"]:
        raise BookingError("Could not save the appointment. Please try again.")
    return resp["data"][0]
