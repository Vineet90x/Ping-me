import logging

from fastapi import APIRouter, HTTPException

from config import now_ist
from models.invoice import InvoiceCreate, InvoiceResponse
from services import invoicing
from services.database import get_db
from services.invoicing import InvoiceError

logger = logging.getLogger("ping.invoices")
router = APIRouter()


@router.post("/{salon_id}/invoices", response_model=InvoiceResponse)
def create_invoice(salon_id: str, invoice: InvoiceCreate):
    db = get_db()

    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    salon = salon_response["data"][0]

    try:
        created = invoicing.create_invoice(
            db,
            salon_id=salon_id,
            customer_id=invoice.customer_id,
            amount=invoice.amount,
            description=invoice.description,
            appointment_id=invoice.appointment_id,
        )
    except InvoiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {**created, **invoicing.links(salon, created)}


@router.get("/{salon_id}/invoices")
def list_invoices(salon_id: str, status: str | None = None):
    db = get_db()
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")

    query = db.table("invoices").eq("salon_id", salon_id)
    if status:
        if status not in ("paid", "unpaid"):
            raise HTTPException(status_code=400, detail="Invalid status filter")
        query = query.eq("payment_status", status)
    return query.order("created_at", desc=True).execute()["data"]


@router.patch("/{salon_id}/invoices/{invoice_id}")
def update_invoice_status(salon_id: str, invoice_id: str, payment_status: str):
    db = get_db()
    if payment_status not in ("unpaid", "paid"):
        raise HTTPException(status_code=400, detail="Invalid status")

    response = db.table("invoices").eq("id", invoice_id).eq("salon_id", salon_id).execute()
    if not response["data"]:
        raise HTTPException(status_code=404, detail="Invoice not found")

    update_data = {"payment_status": payment_status}
    update_data["paid_at"] = now_ist().isoformat() if payment_status == "paid" else None

    db.table("invoices").eq("id", invoice_id).update(update_data)
    return {"message": "Invoice updated", "payment_status": payment_status}


@router.post("/{salon_id}/invoices/{invoice_id}/pdf")
def generate_invoice_pdf_endpoint(salon_id: str, invoice_id: str):
    """Generate a PDF for the invoice, upload it to storage, and store the URL."""
    db = get_db()

    invoice_resp = db.table("invoices").eq("id", invoice_id).eq("salon_id", salon_id).execute()
    if not invoice_resp["data"]:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice = invoice_resp["data"][0]

    salon_resp = db.table("salons").eq("id", salon_id).execute()
    if not salon_resp["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    salon = salon_resp["data"][0]

    customer_resp = db.table("customers").eq("id", invoice["customer_id"]).execute()
    customer = customer_resp["data"][0] if customer_resp["data"] else {}

    public_url = invoicing.generate_and_store_pdf(db, salon, invoice, customer)
    if not public_url:
        raise HTTPException(
            status_code=502,
            detail="PDF generated but upload failed. Check the storage bucket exists.",
        )

    return {"message": "Invoice PDF generated", "pdf_url": public_url}
