import logging
import os
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("ping.config")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
# Service role key — bypasses RLS, needed for storage uploads.
# Get it from Supabase → Settings → API → service_role (secret).
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or SUPABASE_KEY
SUPABASE_INVOICE_BUCKET = os.getenv("SUPABASE_INVOICE_BUCKET", "invoices")

# Redis
REDIS_URL = os.getenv("REDIS_URL")

# Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

# App
DEBUG = os.getenv("DEBUG", "True").lower() in ("1", "true", "yes")

# REST API guard: requests to /api/salons/* must send this as the X-API-Key header.
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

# When true, the WhatsApp webhook rejects requests without a valid Twilio
# signature. Keep off for local ngrok testing; turn on in production.
VERIFY_TWILIO_SIGNATURE = os.getenv("VERIFY_TWILIO_SIGNATURE", "False").lower() in ("1", "true", "yes")

# Comma-separated list of allowed CORS origins (e.g. the dashboard URL).
# Defaults to "*" so local development keeps working.
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# Public base URL of this API (used to build tappable https payment links that
# redirect into UPI apps). Falls back to localhost for dev.
PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL") or "http://localhost:8800").rstrip("/")

# All salons operate in India; bookings are interpreted in IST.
IST = timezone(timedelta(hours=5, minutes=30))

# Defaults used when a salon has no `settings` row.
DEFAULT_OPENING_TIME = "10:00"
DEFAULT_CLOSING_TIME = "20:00"
DEFAULT_DAYS_ADVANCE = 30
DEFAULT_MIN_ADVANCE_MINUTES = 60


def now_ist() -> datetime:
    """Current time as a naive datetime in IST (matches how times are stored)."""
    return datetime.now(IST).replace(tzinfo=None)


def validate_config() -> list[str]:
    """Return a list of missing-but-required env vars (for startup warnings)."""
    required = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
    }
    missing = [name for name, val in required.items() if not val]
    if not REDIS_URL:
        logger.warning("REDIS_URL not set — sessions fall back to in-memory (single process only)")
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_NUMBER):
        logger.warning("Twilio not fully configured — outgoing WhatsApp messages will be skipped")
    if not ADMIN_API_KEY:
        logger.warning("ADMIN_API_KEY not set — the REST API is UNPROTECTED (any caller can use it)")
    return missing


class _DropWebhookAccessLog(logging.Filter):
    """Hide the repetitive `POST /api/webhooks/whatsapp 200` uvicorn access line.

    Every WhatsApp message produces one of these; they drown out the app's own
    one-line-per-message log. The webhook handler logs its own concise summary.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return "/api/webhooks/whatsapp" not in record.getMessage()


def configure_logging() -> None:
    """Set sensible log levels: app logs readable, third-party noise silenced.

    The previous setup routed the *root* logger to DEBUG whenever DEBUG=True,
    which made httpx/httpcore log every Supabase and Twilio request on every
    chat message. Here we only raise verbosity for our own ``ping.*`` loggers.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app_level = logging.DEBUG if DEBUG else logging.INFO
    logging.getLogger("ping").setLevel(app_level)

    # These are chatty at INFO/DEBUG and add nothing during normal operation.
    for noisy in ("httpx", "httpcore", "twilio", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("uvicorn.access").addFilter(_DropWebhookAccessLog())
