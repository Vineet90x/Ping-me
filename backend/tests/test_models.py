import pytest
from pydantic import ValidationError

from models.service import ServiceCreate
from models.invoice import InvoiceCreate
from models.salon import SalonRegister


def test_service_price_minimum_is_one_rupee():
    # 100 paise == ₹1 must be accepted (the old code rejected it).
    assert ServiceCreate(service_name="Haircut", price=100, duration_minutes=30).price == 100


def test_service_price_below_one_rupee_rejected():
    with pytest.raises(ValidationError):
        ServiceCreate(service_name="Haircut", price=99, duration_minutes=30)


def test_service_duration_bounds():
    with pytest.raises(ValidationError):
        ServiceCreate(service_name="Spa", price=500, duration_minutes=0)
    with pytest.raises(ValidationError):
        ServiceCreate(service_name="Spa", price=500, duration_minutes=500)


def test_invoice_amount_minimum():
    assert InvoiceCreate(customer_id="c1", amount=100).amount == 100
    with pytest.raises(ValidationError):
        InvoiceCreate(customer_id="c1", amount=99)


def test_salon_phone_validation():
    SalonRegister(owner_phone="9136275825", owner_name="Neha", salon_name="Neha Salon")
    with pytest.raises(ValidationError):
        SalonRegister(owner_phone="12345", owner_name="Neha", salon_name="Neha Salon")


def test_salon_upi_validation():
    SalonRegister(owner_phone="9136275825", owner_name="Neha", salon_name="Neha Salon", upi_id="neha@okhdfc")
    with pytest.raises(ValidationError):
        SalonRegister(owner_phone="9136275825", owner_name="Neha", salon_name="Neha Salon", upi_id="not-a-upi")
