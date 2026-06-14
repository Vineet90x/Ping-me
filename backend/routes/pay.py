"""Public payment redirect: turns a tappable https link into a UPI app open.

A customer taps ``https://<host>/pay/<invoice_id>`` in WhatsApp; this endpoint
looks up the invoice + salon's UPI id and 302-redirects to the ``upi://pay?...``
deep link, which opens GPay/PhonePe/Paytm with the amount pre-filled.
"""
import logging

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from services import payments
from services.database import get_db

logger = logging.getLogger("ping.pay")
router = APIRouter()


def _fallback_page(message: str) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html><body style='font-family:sans-serif;text-align:center;"
        f"padding:40px'><h2>Ping</h2><p>{message}</p></body></html>",
        status_code=200,
    )


@router.get("/pay/{invoice_id}")
def pay_redirect(invoice_id: str):
    db = get_db()
    invoice = db.table("invoices").eq("id", invoice_id).execute()["data"]
    if not invoice:
        return _fallback_page("This payment link is invalid or has expired.")
    invoice = invoice[0]

    if invoice.get("payment_status") == "paid":
        return _fallback_page("This invoice is already paid. Thank you! 🙏")

    salon = db.table("salons").eq("id", invoice["salon_id"]).execute()["data"]
    salon = salon[0] if salon else {}

    deep_link = payments.upi_deep_link(
        salon.get("upi_id"), invoice["amount"], invoice["id"], salon.get("salon_name")
    )
    if not deep_link:
        return _fallback_page("This salon hasn't set up UPI payments yet.")

    return RedirectResponse(url=deep_link, status_code=302)
