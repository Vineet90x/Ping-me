from pydantic import BaseModel, validator
import re

class SalonRegister(BaseModel):
    owner_phone: str
    owner_name: str
    salon_name: str
    upi_id: str = None
    
    @validator('owner_phone')
    def validate_phone(cls, v):
        if not re.match(r'^\d{10}$', v):
            raise ValueError('Phone must be 10 digits')
        return v
    
    @validator('owner_name')
    def validate_owner_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Owner name must be at least 2 characters')
        return v.strip()
    
    @validator('salon_name')
    def validate_salon_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Salon name must be at least 2 characters')
        return v.strip()
    
    @validator('upi_id')
    def validate_upi(cls, v):
        if v and not re.match(r'^[a-zA-Z0-9.\-_]+@[a-zA-Z]{3,}$', v):
            raise ValueError('Invalid UPI format (e.g., name@bank)')
        return v
    
    @validator('owner_name', 'salon_name')
    def validate_names(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        if len(v.strip()) < 2:
            raise ValueError('Must be at least 2 characters')
        return v.strip()    

class SalonUpdate(BaseModel):
    owner_name: str = None
    salon_name: str = None
    upi_id: str = None
    
    @validator('owner_name')
    def validate_owner_name(cls, v):
        if v and len(v.strip()) < 2:
            raise ValueError('Owner name must be at least 2 characters')
        return v.strip() if v else None
    
    @validator('salon_name')
    def validate_salon_name(cls, v):
        if v and len(v.strip()) < 2:
            raise ValueError('Salon name must be at least 2 characters')
        return v.strip() if v else None
    
    @validator('upi_id')
    def validate_upi(cls, v):
        if v and not re.match(r'^[a-zA-Z0-9.\-_]+@[a-zA-Z]{3,}$', v):
            raise ValueError('Invalid UPI format')
        return v
    
class SalonResponse(BaseModel):
    id: str
    owner_phone: str
    owner_name: str
    salon_name: str
    plan_type: str