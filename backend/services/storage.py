"""Upload generated files (PDF invoices, images) to Supabase Storage.

Best-effort: on any failure we log and return ``None`` so the caller can carry
on without a public URL rather than failing the whole request.
"""
import logging

import httpx

from config import SUPABASE_SERVICE_KEY, SUPABASE_URL

logger = logging.getLogger("ping.storage")


def upload_bytes(bucket: str, path: str, data: bytes, content_type: str) -> str | None:
    """Upload ``data`` to ``bucket/path`` and return its public URL, or None."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        logger.info("Storage not configured; skipping upload of %s/%s", bucket, path)
        return None

    base = SUPABASE_URL.rstrip("/")
    url = f"{base}/storage/v1/object/{bucket}/{path}"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    try:
        resp = httpx.post(url, content=data, headers=headers, timeout=30.0)
        if resp.status_code not in (200, 201):
            logger.error("Storage upload %s -> %s: %s", path, resp.status_code, resp.text)
            return None
    except httpx.HTTPError as exc:
        logger.error("Storage upload failed for %s: %s", path, exc)
        return None

    return f"{base}/storage/v1/object/public/{bucket}/{path}"
