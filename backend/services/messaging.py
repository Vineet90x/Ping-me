"""WhatsApp messaging via Twilio.

Centralises the Twilio client so the webhook, broadcasts and reminder jobs all
send the same way. Safe to import even when Twilio isn't configured — sends are
logged and skipped instead of crashing (useful for local/dev runs).
"""
import logging

from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER

logger = logging.getLogger("ping.messaging")

_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        from twilio.rest import Client

        _client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except Exception as exc:  # pragma: no cover - depends on infra
        logger.warning("Could not init Twilio client: %s", exc)


def _to_whatsapp(number: str) -> str:
    """Ensure the number carries the ``whatsapp:`` prefix Twilio expects."""
    number = number.strip()
    return number if number.startswith("whatsapp:") else f"whatsapp:{number}"


def send_whatsapp(to_number: str, body: str, media_url: str | None = None) -> bool:
    """Send a WhatsApp message. Returns True on success, False otherwise."""
    if not _client or not TWILIO_WHATSAPP_NUMBER:
        logger.info("[whatsapp skipped] to=%s body=%s", to_number, body[:80])
        return False
    try:
        kwargs = {
            "body": body,
            "from_": _to_whatsapp(TWILIO_WHATSAPP_NUMBER),
            "to": _to_whatsapp(to_number),
        }
        if media_url:
            kwargs["media_url"] = [media_url]
        _client.messages.create(**kwargs)
        return True
    except Exception as exc:
        logger.error("Failed to send WhatsApp to %s: %s", to_number, exc)
        return False
