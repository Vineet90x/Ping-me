import logging
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import CORS_ORIGINS, DEBUG, configure_logging, validate_config
from services.auth import require_api_key
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
    pay,
)

configure_logging()
logger = logging.getLogger("ping")

app = FastAPI(title="Ping Salon Booking API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Simple in-process rate limiter (no extra dependencies).
# Tracks request timestamps per IP in a sliding window.
# ---------------------------------------------------------------------------
_rate_lock = Lock()
_rate_store: dict[str, deque] = defaultdict(deque)

RATE_LIMITS = {
    "/api/webhooks/whatsapp": (30, 60),   # 30 req / 60s  (Twilio sends fast)
    "/api/salons/register":   (5, 60),    # 5 registrations / 60s
    "default":                (120, 60),  # 120 req / 60s for everything else
}


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    ip = request.client.host if request.client else "unknown"
    path = request.url.path
    max_req, window = RATE_LIMITS.get(path) or RATE_LIMITS["default"]
    now = time.monotonic()

    with _rate_lock:
        q = _rate_store[ip]
        while q and q[0] < now - window:
            q.popleft()
        if len(q) >= max_req:
            logger.warning("Rate limit hit: %s on %s (%d req/%ds)", ip, path, max_req, window)
            return JSONResponse(status_code=429, content={"detail": "Too many requests. Please slow down."})
        q.append(now)

    return await call_next(request)


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


# The salon management API is guarded by an API key (X-API-Key header).
_guard = [Depends(require_api_key)]
app.include_router(salons.router, prefix="/api/salons", tags=["Salons"], dependencies=_guard)
app.include_router(staff.router, prefix="/api/salons", tags=["Staff"], dependencies=_guard)
app.include_router(services.router, prefix="/api/salons", tags=["Services"], dependencies=_guard)
app.include_router(appointments.router, prefix="/api/salons", tags=["Appointments"], dependencies=_guard)
app.include_router(invoices.router, prefix="/api/salons", tags=["Invoices"], dependencies=_guard)
app.include_router(broadcasts.router, prefix="/api/salons", tags=["Broadcasts"], dependencies=_guard)
app.include_router(settings.router, prefix="/api/salons", tags=["Settings"], dependencies=_guard)

# Public, unguarded: Twilio can't send custom headers (webhook has its own
# signature check) and the payment redirect is opened by customers' phones.
app.include_router(webhook.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(pay.router, tags=["Payments"])


@app.get("/")
def root():
    return {"message": "Ping API running", "version": app.version}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8800, reload=True)
