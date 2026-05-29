from pydantic import BaseModel, field_validator
from typing import Optional

# Amounts are stored in paise (100 paise = ₹1). Minimum invoice is ₹1.
MIN_AMOUNT_PAISE = 100


class InvoiceCreate(BaseModel):
    customer_id: str
    amount: int  # in paise
    description: Optional[str] = None
    appointment_id: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        if v < MIN_AMOUNT_PAISE:
            raise ValueError("Amount must be at least ₹1 (100 paise)")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        if v is None:
            return None
        v = v.strip()
        if len(v) > 200:
            raise ValueError("Description max 200 characters")
        return v or None

    @field_validator("customer_id", "appointment_id")
    @classmethod
    def validate_ids(cls, v):
        if v is not None and not v.strip():
            raise ValueError("ID cannot be empty")
        return v


class InvoiceResponse(BaseModel):
    id: str
    salon_id: str
    customer_id: str
    amount: int
    description: Optional[str] = None
    payment_status: str
    pdf_url: Optional[str] = None
    upi_link: Optional[str] = None
