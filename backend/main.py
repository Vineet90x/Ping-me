from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import salons, staff

app = FastAPI(title="Ping Salon Booking API", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(salons.router, prefix="/api/salons", tags=["Salons"])
app.include_router(staff.router, prefix="/api/staff", tags=["Staff"])

@app.get("/")
def root():
    return {"message": "Ping API running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)