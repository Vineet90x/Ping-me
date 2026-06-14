"""Seed the database with a demo salon, services, staff and settings so you can
walk through the WhatsApp booking flow like a real customer.

Run from the backend/ directory with your venv active:

    python seed_data.py

It is idempotent — re-running won't create duplicates (it matches the salon by
owner phone, and services/staff by name).

NOTE on multi-salon behaviour:
  - If only ONE salon exists, the bot auto-selects it after "hi".
  - If more than one exists, the bot shows a numbered salon menu first.
  So if you already have other salons in the DB, expect a salon-picker step.
"""
from services.database import DBError, get_db

# --- Edit these to taste ---------------------------------------------------
# Set OWNER_PHONE to YOUR WhatsApp number (10 digits, no +91) if you want to
# test the OWNER commands (STATS / TOMORROW / UNPAID). If you text from this
# number you'll be treated as the owner; from any other number, as a customer.
OWNER_PHONE = "9136275825"
OWNER_NAME = "Neha"
SALON_NAME = "Neha's Beauty Salon"
UPI_ID = "neha@okhdfc"

# (service name, price in paise [100 = Rs.1], duration in minutes)
SERVICES = [
    ("Beard Trim", 15000, 20),
    ("Haircut", 40000, 45),
    ("Hair Spa", 80000, 60),
    ("Hair Color", 150000, 90),
]

STAFF = ["Rakesh", "Priya", "Sana"]

SETTINGS = {
    "opening_time": "10:00",
    "closing_time": "20:00",
    "days_advance_booking": 30,
    "min_advance_booking_minutes": 60,
}
# ---------------------------------------------------------------------------


def main():
    db = get_db()

    # 1) Salon — find by owner phone, else create.
    existing = db.table("salons").eq("owner_phone", OWNER_PHONE).execute()["data"]
    if existing:
        salon = existing[0]
        print(f"Salon already exists: {salon['salon_name']} ({salon['id']})")
    else:
        salon = db.table("salons").insert(
            {
                "owner_phone": OWNER_PHONE,
                "owner_name": OWNER_NAME,
                "salon_name": SALON_NAME,
                "upi_id": UPI_ID,
                "plan_type": "free",
                "subscription_active": True,
            }
        )["data"][0]
        print(f"Created salon: {salon['salon_name']} ({salon['id']})")
    salon_id = salon["id"]

    # 2) Settings — upsert.
    if db.table("settings").eq("salon_id", salon_id).execute()["data"]:
        db.table("settings").eq("salon_id", salon_id).update(SETTINGS)
        print("Updated settings")
    else:
        db.table("settings").insert({**SETTINGS, "salon_id": salon_id})
        print("Created settings")

    # 3) Services — add any that don't already exist (by name).
    have = {s["service_name"].lower() for s in db.table("services").eq("salon_id", salon_id).execute()["data"]}
    for name, price, duration in SERVICES:
        if name.lower() in have:
            print(f"  service exists: {name}")
            continue
        db.table("services").insert(
            {
                "salon_id": salon_id,
                "service_name": name,
                "price": price,
                "duration_minutes": duration,
                "is_active": True,
            }
        )
        print(f"  + service: {name} (Rs.{price / 100:.0f}, {duration} min)")

    # 4) Staff — add any that don't already exist (by name).
    have = {s["staff_name"].lower() for s in db.table("staff").eq("salon_id", salon_id).execute()["data"]}
    for name in STAFF:
        if name.lower() in have:
            print(f"  staff exists: {name}")
            continue
        db.table("staff").insert({"salon_id": salon_id, "staff_name": name, "is_active": True})
        print(f"  + staff: {name}")

    print("\n✅ Done! Message your Twilio WhatsApp sandbox with 'hi' to start booking.")
    print(f"   Salon ID    : {salon_id}")
    print(f"   Owner phone : {OWNER_PHONE}  (text from this number to try STATS / TOMORROW / UNPAID)")


if __name__ == "__main__":
    try:
        main()
    except DBError as exc:
        print(f"Database error: {exc}")
