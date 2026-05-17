from pydantic import BaseModel, validator
from datetime import date, time

class AppointmentCreate(BaseModel):
    customer_phone: str
    customer_name: str
    service_id: str
    staff_id: str
    appointment_date: date
    appointment_time: time
    
    @validator('customer_phone')
    def validate_phone(cls, v):
        import re
        if not re.match(r'^\d{10}$', v):
            raise ValueError('Phone must be 10 digits')
        return v
    
    @validator('customer_name')
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Customer name must be at least 2 characters')
        return v.strip()
    
    @validator('appointment_date')
    def validate_date(cls, v):
        from datetime import datetime, timedelta
        today = datetime.now().date()
        if v < today:
            raise ValueError('Cannot book in the past')
        if v > today + timedelta(days=30):
            raise ValueError('Cannot book more than 30 days in advance')
        return v

class AppointmentResponse(BaseModel):
    id: str
    salon_id: str
    customer_id: str
    service_id: str
    staff_id: str
    appointment_date: date
    appointment_time: time
    status: str