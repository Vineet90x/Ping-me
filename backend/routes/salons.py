from fastapi import APIRouter, Depends, HTTPException

from models.salon import SalonRegister, SalonResponse, SalonUpdate
from services.auth import generate_api_key, get_current_salon
from services.database import get_db

router = APIRouter()


@router.get("/me", response_model=SalonResponse)
def get_my_salon(current_salon: dict | None = Depends(get_current_salon)):
    """Return the salon that owns the current API key.

    The Next.js dashboard calls this after login to resolve salon_id and
    display the salon name without the owner having to know their UUID.
    """
    if current_salon is None:
        raise HTTPException(status_code=403, detail="Admin key has no salon context. Use a salon API key.")
    return current_salon


@router.get("")
def list_salons(limit: int = 100):
    """List all salons (admin use only — guarded by the global ADMIN_API_KEY)."""
    db = get_db()
    return db.table("salons").order("salon_name").limit(limit).execute()["data"]


@router.post("/register", response_model=SalonResponse, status_code=201)
def register_salon(salon: SalonRegister):
    """Register a new salon. Returns the salon record including the api_key.

    The api_key is the owner's credential for the dashboard — save it. It is
    also accessible later via GET /api/salons/me using that same key.
    """
    db = get_db()

    existing = db.table("salons").eq("owner_phone", salon.owner_phone).execute()
    if existing["data"]:
        raise HTTPException(status_code=400, detail="A salon with this phone number already exists.")

    key = generate_api_key()
    response = db.table("salons").insert({
        "owner_phone": salon.owner_phone,
        "owner_name": salon.owner_name,
        "salon_name": salon.salon_name,
        "upi_id": salon.upi_id,
        "plan_type": "free",
        "api_key": key,
    })

    if not response["data"]:
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")

    return response["data"][0]


@router.get("/by-phone/{owner_phone}")
def get_salon_by_phone(owner_phone: str):
    """Look up a salon by the owner's phone number (used for dashboard login flow)."""
    db = get_db()
    response = db.table("salons").eq("owner_phone", owner_phone).execute()

    if not response["data"]:
        raise HTTPException(status_code=404, detail="No salon found for this phone number.")

    return response["data"][0]


@router.get("/{salon_id}", response_model=SalonResponse)
def get_salon(salon_id: str):
    db = get_db()
    response = db.table("salons").eq("id", salon_id).execute()

    if not response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found.")

    return response["data"][0]


@router.get("/{salon_id}/customers")
def list_customers(salon_id: str):
    """List a salon's customers (for the dashboard name lookups)."""
    db = get_db()
    if not db.table("salons").eq("id", salon_id).execute()["data"]:
        raise HTTPException(status_code=404, detail="Salon not found.")
    return db.table("customers").eq("salon_id", salon_id).order("customer_name").execute()["data"]


@router.patch("/{salon_id}", response_model=SalonResponse)
def update_salon(salon_id: str, salon: SalonUpdate):
    db = get_db()

    if not db.table("salons").eq("id", salon_id).execute()["data"]:
        raise HTTPException(status_code=404, detail="Salon not found.")

    update_data = {}
    if salon.owner_name is not None:
        update_data["owner_name"] = salon.owner_name
    if salon.salon_name is not None:
        update_data["salon_name"] = salon.salon_name
    if salon.upi_id is not None:
        update_data["upi_id"] = salon.upi_id

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update.")

    result = db.table("salons").eq("id", salon_id).update(update_data)
    if not result["data"]:
        raise HTTPException(status_code=500, detail="Update failed.")

    return result["data"][0]
