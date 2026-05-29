import logging
import os
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("ping.config")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_INVOICE_BUCKET = os.getenv("SUPABASE_INVOICE_BUCKET", "invoices")

# Redis
REDIS_URL = os.getenv("REDIS_URL")

# Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

# App
DEBUG = os.getenv("DEBUG", "True").lower() in ("1", "true", "yes")

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
    return missing
