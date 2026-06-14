"""Authentication helpers for the REST API and the WhatsApp webhook.

REST API uses two tiers:
  - Global ADMIN_API_KEY: backwards-compatible, grants access to every salon
    (use only for admin tooling / the seed script).
  - Per-salon API key: generated on registration, scoped to that salon. The
    Next.js dashboard sends this in X-API-Key and calls /api/salons/me to
    identify which salon it is.

When the ADMIN_API_KEY env var is unset the guard is disabled (with a startup
warning) so local development isn't blocked by missing config.
"""
import hmac
import logging
import secrets

from fastapi import Header, HTTPException, Request, status

from config import ADMIN_API_KEY, TWILIO_AUTH_TOKEN, VERIFY_TWILIO_SIGNATURE

logger = logging.getLogger("ping.auth")


def generate_api_key() -> str:
    """Return a cryptographically random 43-character URL-safe key."""
    return secrets.token_urlsafe(32)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency: reject requests without a valid API key.

    Accepts either the global ADMIN_API_KEY or any salon's per-salon key.
    When ADMIN_API_KEY is unset the guard is disabled for local dev.
    """
    if not ADMIN_API_KEY:
        return

    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    # Fast path: check the global admin key first (constant-time compare).
    if hmac.compare_digest(x_api_key, ADMIN_API_KEY):
        return

    # Per-salon key: hit the DB once to validate.
    from services.database import DBError, get_db  # local import to avoid circular deps
    try:
        db = get_db()
        salons = db.table("salons").eq("api_key", x_api_key).execute()["data"]
        if salons:
            return
    except DBError:
        pass  # DB unreachable → treat the unknown key as invalid

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def get_current_salon(x_api_key: str | None = Header(default=None)) -> dict | None:
    """FastAPI dependency: return the salon dict for a per-salon key.

    Returns None when called with the global ADMIN_API_KEY (no salon context).
    Raises 401 if the key is missing or invalid.
    Use this on endpoints that need to know *which* salon is calling.
    """
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    # Admin key is valid but has no salon context.
    if ADMIN_API_KEY and hmac.compare_digest(x_api_key, ADMIN_API_KEY):
        return None

    from services.database import DBError, get_db
    try:
        db = get_db()
        salons = db.table("salons").eq("api_key", x_api_key).execute()["data"]
        if salons:
            return salons[0]
    except DBError:
        pass

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


async def verify_twilio_signature(request: Request, body: bytes) -> bool:
    """Validate Twilio's X-Twilio-Signature for an inbound webhook request.

    Returns True when the signature is valid OR verification is turned off.
    """
    if not VERIFY_TWILIO_SIGNATURE:
        return True
    if not TWILIO_AUTH_TOKEN:
        logger.warning("VERIFY_TWILIO_SIGNATURE is on but TWILIO_AUTH_TOKEN is missing")
        return False

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        return False

    try:
        from twilio.request_validator import RequestValidator
        from urllib.parse import parse_qsl

        validator = RequestValidator(TWILIO_AUTH_TOKEN)
        url = str(request.url)
        params = dict(parse_qsl(body.decode("utf-8")))
        return validator.validate(url, params, signature)
    except Exception as exc:  # pragma: no cover
        logger.error("Twilio signature validation error: %s", exc)
        return False
