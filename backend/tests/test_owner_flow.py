"""Tests for the new owner-side WhatsApp features, payment loop, opt-out,
banners and the REST API-key guard. All run against in-memory fakes — no network.
"""
import pytest

from routes import webhook
from services import auth
from models.broadcaste import BroadcastCreate
from services import banners
from tests.fakes import FakeDB, FakeSession


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture
def db_with_salon():
    db = FakeDB()
    salon = db.table("salons").insert(
        {"owner_phone": "9000000000", "owner_name": "Neha", "salon_name": "Neha Salon", "upi_id": "neha@ok"}
    )["data"][0]
    service = db.table("services").insert(
        {"salon_id": salon["id"], "service_name": "Haircut", "price": 40000, "duration_minutes": 45, "is_active": True}
    )["data"][0]
    customer = db.table("customers").insert(
        {"salon_id": salon["id"], "phone": "9870000001", "customer_name": "Asha", "opted_out_broadcasts": False}
    )["data"][0]
    return db, salon, service, customer


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Never hit Twilio or Supabase storage during these tests."""
    monkeypatch.setattr(webhook, "send_whatsapp", lambda *a, **k: True)
    monkeypatch.setattr(webhook.invoicing, "generate_and_store_pdf", lambda *a, **k: "http://pdf/test.pdf")


# --------------------------------------------------------------------------- #
# Amount parsing
# --------------------------------------------------------------------------- #
def test_parse_rupees_to_paise():
    assert webhook._parse_rupees_to_paise("1200") == 120000
    assert webhook._parse_rupees_to_paise("₹1,200.50") == 120050
    assert webhook._parse_rupees_to_paise("abc") is None
    assert webhook._parse_rupees_to_paise("0") is None        # below ₹1 minimum
    assert webhook._parse_rupees_to_paise("0.50") is None      # 50 paise < 100


# --------------------------------------------------------------------------- #
# BILL flow (owner invoicing)
# --------------------------------------------------------------------------- #
def test_bill_flow_creates_unpaid_invoice(db_with_salon):
    db, salon, service, customer = db_with_salon
    today = webhook.now_ist().date()
    db.table("appointments").insert(
        {
            "salon_id": salon["id"],
            "customer_id": customer["id"],
            "service_id": service["id"],
            "staff_id": "staff-1",
            "appointment_date": str(today),
            "appointment_time": "11:00",
            "status": "completed",
        }
    )
    session = FakeSession()

    out = webhook._bill_start(db, session, salon)
    assert "Asha" in out and session.get()["owner_step"] == "bill_pick"

    out = webhook._bill_pick(db, session, session.get(), salon, "1")
    assert session.get()["owner_step"] == "bill_amount"

    out = webhook._bill_amount(db, session, session.get(), salon, "OK")  # accept ₹400 default
    assert session.get()["owner_step"] == "bill_status"
    assert session.get()["bill_amount"] == 40000

    out = webhook._bill_status(db, session, session.get(), salon, "3")  # not paid yet
    invoices = db.table("invoices").execute()["data"]
    assert len(invoices) == 1
    assert invoices[0]["payment_status"] == "unpaid"
    assert invoices[0]["amount"] == 40000
    assert "INV-" in out
    assert session.get() is None  # session cleared


def test_bill_walkin_by_phone_marks_paid(db_with_salon):
    db, salon, service, customer = db_with_salon
    session = FakeSession()
    session.set({"owner_step": "bill_pick", "salon_id": salon["id"], "bill_options": []})

    out = webhook._bill_pick(db, session, session.get(), salon, "0")
    assert session.get()["owner_step"] == "bill_phone"

    out = webhook._bill_phone(db, session, session.get(), salon, "9870000099")
    assert session.get()["owner_step"] == "bill_amount"

    out = webhook._bill_amount(db, session, session.get(), salon, "550")
    assert session.get()["bill_amount"] == 55000

    webhook._bill_status(db, session, session.get(), salon, "2")  # cash, already paid
    invoices = db.table("invoices").execute()["data"]
    assert invoices[0]["payment_status"] == "paid"
    assert invoices[0]["amount"] == 55000


def test_bill_amount_rejects_garbage(db_with_salon):
    db, salon, _, _ = db_with_salon
    session = FakeSession()
    session.set({"owner_step": "bill_amount", "salon_id": salon["id"], "bill_default_amount": 0,
                 "bill_customer_name": "Asha"})
    out = webhook._bill_amount(db, session, session.get(), salon, "lots")
    assert "valid amount" in out.lower()
    assert session.get()["owner_step"] == "bill_amount"  # stays put


# --------------------------------------------------------------------------- #
# PAID confirmation loop
# --------------------------------------------------------------------------- #
def test_customer_reports_paid_alerts_owner(db_with_salon, monkeypatch):
    db, salon, service, customer = db_with_salon
    db.table("invoices").insert(
        {"salon_id": salon["id"], "customer_id": customer["id"], "amount": 40000,
         "payment_status": "unpaid", "created_at": "2026-06-06T10:00:00"}
    )
    sent = []
    monkeypatch.setattr(webhook, "send_whatsapp", lambda to, body, **k: sent.append((to, body)) or True)

    out = webhook._customer_reports_paid(db, "9870000001")
    assert "let the salon know" in out.lower()
    assert sent and sent[0][0] == "+919000000000"  # owner alerted
    assert "PAID" in sent[0][1]


def test_customer_reports_paid_no_invoice(db_with_salon):
    db, salon, service, customer = db_with_salon
    out = webhook._customer_reports_paid(db, "9870000001")
    assert "don't see" in out.lower()


def test_owner_confirm_paid_marks_invoice(db_with_salon):
    db, salon, service, customer = db_with_salon
    inv = db.table("invoices").insert(
        {"salon_id": salon["id"], "customer_id": customer["id"], "amount": 40000, "payment_status": "unpaid"}
    )["data"][0]
    code = webhook.payments.invoice_code(inv["id"])

    out = webhook._owner_confirm_paid(db, salon, f"PAID {code}")
    assert "marked paid" in out.lower()
    assert db.table("invoices").eq("id", inv["id"]).execute()["data"][0]["payment_status"] == "paid"


def test_owner_confirm_paid_unknown_code(db_with_salon):
    db, salon, _, _ = db_with_salon
    out = webhook._owner_confirm_paid(db, salon, "PAID ZZZZ9999")
    assert "no unpaid invoice" in out.lower()


# --------------------------------------------------------------------------- #
# STOP opt-out
# --------------------------------------------------------------------------- #
def test_handle_stop_opts_out_all_rows(db_with_salon):
    db, salon, service, customer = db_with_salon
    # Same phone, a second salon.
    db.table("customers").insert(
        {"salon_id": "salon-2", "phone": "9870000001", "customer_name": "Asha", "opted_out_broadcasts": False}
    )
    out = webhook._handle_stop(db, "9870000001")
    assert "unsubscribed" in out.lower()
    rows = db.table("customers").eq("phone", "9870000001").execute()["data"]
    assert all(r["opted_out_broadcasts"] for r in rows)


# --------------------------------------------------------------------------- #
# Banner generation + model validation
# --------------------------------------------------------------------------- #
def test_banner_returns_png_bytes():
    data = banners.generate_offer_banner("Neha Salon", "Weekend 20% off", "Sat & Sun only")
    assert data[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic header


def test_broadcast_headline_too_long():
    with pytest.raises(ValueError):
        BroadcastCreate(message_text="hello there", headline="x" * 81)


def test_broadcast_headline_trimmed():
    b = BroadcastCreate(message_text="hello there", headline="  Big Sale  ")
    assert b.headline == "Big Sale"


# --------------------------------------------------------------------------- #
# API-key guard
# --------------------------------------------------------------------------- #
def test_api_key_disabled_when_unset(monkeypatch):
    monkeypatch.setattr(auth, "ADMIN_API_KEY", None)
    assert auth.require_api_key(None) is None  # no key configured -> allowed


def test_api_key_required_when_set(monkeypatch):
    monkeypatch.setattr(auth, "ADMIN_API_KEY", "secret")
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        auth.require_api_key(None)
    with pytest.raises(HTTPException):
        auth.require_api_key("wrong")
    assert auth.require_api_key("secret") is None  # correct key passes
