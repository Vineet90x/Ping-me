from pydantic import BaseModel, field_validator

# Prices are stored in paise (100 paise = ₹1). Minimum service price is ₹1.
MIN_PRICE_PAISE = 100


class ServiceCreate(BaseModel):
    service_name: str
    price: int  # in paise (100 = ₹1)
    duration_minutes: int

    @field_validator("service_name")
    @classmethod
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError("Service name must be at least 2 characters")
        return v.strip()

    @field_validator("price")
    @classmethod
    def validate_price(cls, v):
        if v < MIN_PRICE_PAISE:
            raise ValueError("Price must be at least ₹1 (100 paise)")
        return v

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration(cls, v):
        if v <= 0 or v > 480:  # Max 8 hours
            raise ValueError("Duration must be between 1 and 480 minutes")
        return v


class ServiceResponse(BaseModel):
    id: str
    service_name: str
    price: int
    duration_minutes: int
    salon_id: str
    is_active: bool
