"""UPI payment-link helpers.

UPI deep links (``upi://pay?...``) open straight into GPay/PhonePe/Paytm with the
amount pre-filled, but WhatsApp won't render a ``upi://`` URL as tappable. So we
also expose an ``https`` link (``/pay/{invoice_id}``) that redirects to the deep
link — that one *is* tappable in chat. Both are built here so the REST API and the
bot stay consistent.
"""
from urllib.parse import quote

from config import PUBLIC_BASE_URL


def invoice_code(invoice_id) -> str:
    """Short human-facing code for an invoice (first 8 chars of its id)."""
    return str(invoice_id)[:8].upper()


def upi_deep_link(upi_id: str | None, amount_paise: int, invoice_id, payee_name: str | None = None) -> str | None:
    """Build a ``upi://pay`` deep link, or None if the salon has no UPI id."""
    if not upi_id:
        return None
    amount_rupees = f"{amount_paise / 100:.2f}"
    pn = quote(payee_name or "Salon")
    tr = f"INV-{invoice_code(invoice_id)}"
    return f"upi://pay?pa={upi_id}&pn={pn}&am={amount_rupees}&cu=INR&tn={tr}&tr={tr}"


def pay_url(invoice_id) -> str:
    """Tappable https link that redirects into the customer's UPI app."""
    return f"{PUBLIC_BASE_URL}/pay/{invoice_id}"
