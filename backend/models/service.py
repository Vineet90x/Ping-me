from pydantic import BaseModel, validator

class ServiceCreate(BaseModel):
    service_name: str
    price: int  # in paise (100 = ₹1)
    duration_minutes: int
    
    @validator('service_name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Service name must be at least 2 characters')
        return v.strip()
    
    @validator('price')
    def validate_price(cls, v):
        if v <= 100:
            raise ValueError('Price must be greater than 0')
        return v
    
    @validator('duration_minutes')
    def validate_duration(cls, v):
        if v <= 0 or v > 480:  # Max 8 hours
            raise ValueError('Duration must be between 1 and 480 minutes')
        return v

class ServiceResponse(BaseModel):
    id: str
    service_name: str
    price: int
    duration_minutes: int
    salon_id: str
    is_active: bool