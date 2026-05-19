from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import salons, staff, services, appointments, invoices, broadcasts, settings

app = FastAPI(title="Ping Salon Booking API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(salons.router, prefix="/api/salons", tags=["Salons"])
app.include_router(staff.router, prefix="/api/salons", tags=["Staff"])
app.include_router(services.router, prefix="/api/salons", tags=["Services"])
app.include_router(appointments.router, prefix="/api/salons", tags=["Appointments"])
app.include_router(invoices.router, prefix="/api/salons", tags=["Invoices"])
app.include_router(broadcasts.router, prefix="/api/salons", tags=["Broadcasts"])
app.include_router(settings.router, prefix="/api/salons", tags=["Settings"])

@app.get("/")
def root():
    return {"message": "Ping API running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)