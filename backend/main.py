import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import DEBUG, validate_config
from services.database import DBError
from routes import (
    salons,
    staff,
    services,
    appointments,
    invoices,
    broadcasts,
    settings,
    webhook,
)

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ping")

app = FastAPI(title="Ping Salon Booking API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    missing = validate_config()
    if missing:
        logger.error("Missing required configuration: %s", ", ".join(missing))
    logger.info("Ping API started (debug=%s)", DEBUG)


@app.exception_handler(DBError)
async def db_error_handler(request: Request, exc: DBError):
    """Surface database failures as real HTTP errors instead of empty results."""
    logger.error("DBError on %s %s: %s", request.method, request.url.path, exc.message)
    detail = exc.message if DEBUG else "A database error occurred. Please try again."
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


app.include_router(salons.router, prefix="/api/salons", tags=["Salons"])
app.include_router(staff.router, prefix="/api/salons", tags=["Staff"])
app.include_router(services.router, prefix="/api/salons", tags=["Services"])
app.include_router(appointments.router, prefix="/api/salons", tags=["Appointments"])
app.include_router(invoices.router, prefix="/api/salons", tags=["Invoices"])
app.include_router(broadcasts.router, prefix="/api/salons", tags=["Broadcasts"])
app.include_router(settings.router, prefix="/api/salons", tags=["Settings"])
app.include_router(webhook.router, prefix="/api/webhooks", tags=["Webhooks"])


@app.get("/")
def root():
    return {"message": "Ping API running", "version": app.version}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8800, reload=True)
