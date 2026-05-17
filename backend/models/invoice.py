from pydantic import BaseModel, validator
from typing import Optional

class InvoiceCreate(BaseModel):
    customer_id: str
    amount: int  # in paise
    description: str = None
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        return v
    
    @validator('description')
    def validate_description(cls, v):
        if v and len(v.strip()) > 200:
            raise ValueError('Description max 200 characters')
        return v.strip() if v else None

class InvoiceResponse(BaseModel):
    id: str
    salon_id: str
    customer_id: str
    amount: int
    description: str
    payment_status: str
    pdf_url: Optional[str] = None
    upi_link: Optional[str] = None