from pydantic import BaseModel, validator
import re

class StaffCreate(BaseModel):
    staff_name: str
    phone: str = None
    
    @validator('staff_name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Staff name must be at least 2 characters')
        return v.strip()
    
    @validator('phone')
    def validate_phone(cls, v):
        if v and not re.match(r'^\d{10}$', v):
            raise ValueError('Phone must be 10 digits')
        return v

class StaffResponse(BaseModel):
    id: str
    staff_name: str
    phone: str = None
    salon_id: str
    is_active: bool