"""Shared invoice logic, used by both the REST API and the WhatsApp bot.

Mirrors how ``booking.py`` is shared between the two entry points so the rules
(validation, PDF generation, UPI links) can't drift apart.
"""
import logging

from config import SUPABASE_INVOICE_BUCKET, now_ist
from services import payments, storage
from services.database import DB
from services.pdf import generate_invoice_pdf

logger = logging.getLogger("ping.invoicing")


class InvoiceError(Exception):
    """An invoice could not be created for a validation reason (not a server error)."""


def create_invoice(
    db: DB,
    salon_id: str,
    customer_id: str,
    amount: int,
    description: str | None = None,
    appointment_id: str | None = None,
    payment_status: str = "unpaid",
) -> dict:
    """Validate ownership and insert an invoice row. Returns the created row."""
    customer = db.table("customers").eq("id", customer_id).eq("salon_id", salon_id).execute()["data"]
    if not customer:
        raise InvoiceError("Customer not found for this salon")

    if appointment_id:
        appt = (
            db.table("appointments").eq("id", appointment_id).eq("salon_id", salon_id).execute()["data"]
        )
        if not appt:
            raise InvoiceError("Appointment not found for this salon")

    record = {
        "salon_id": salon_id,
        "customer_id": customer_id,
        "amount": amount,
        "description": description,
        "payment_status": payment_status,
    }
    if appointment_id:
        record["appointment_id"] = appointment_id
    if payment_status == "paid":
        record["paid_at"] = now_ist().isoformat()

    created = db.table("invoices").insert(record)["data"]
    if not created:
        raise InvoiceError("Could not save the invoice. Please try again.")
    return created[0]


def links(salon: dict, invoice: dict) -> dict:
    """Return the UPI deep link + tappable https pay link for an invoice."""
    return {
        "upi_link": payments.upi_deep_link(
            salon.get("upi_id"), invoice["amount"], invoice["id"], salon.get("salon_name")
        ),
        "pay_url": payments.pay_url(invoice["id"]),
    }


def generate_and_store_pdf(db: DB, salon: dict, invoice: dict, customer: dict) -> str | None:
    """Render the invoice PDF, upload it, persist the URL on the invoice. Best effort."""
    try:
        pdf_bytes = generate_invoice_pdf(invoice, salon, customer)
        path = f"{salon['id']}/INV-{payments.invoice_code(invoice['id'])}.pdf"
        public_url = storage.upload_bytes(SUPABASE_INVOICE_BUCKET, path, pdf_bytes, "application/pdf")
        if public_url:
            db.table("invoices").eq("id", invoice["id"]).update({"pdf_url": public_url})
        return public_url
    except Exception as exc:  # pragma: no cover - depends on infra
        logger.error("Invoice PDF generation/upload failed for %s: %s", invoice.get("id"), exc)
        return None
