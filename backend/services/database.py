"""Lightweight Supabase REST client.

Built on httpx because the official Python SDK is unreliable on Windows / 3.12.
The query-builder is intentionally small but supports the operators the app needs:
filtering, ordering, limiting, insert/update/delete.

Unlike a naive client, this one does NOT silently swallow errors. A transport
failure or a 4xx/5xx from Supabase raises ``DBError`` so the caller (or the
global exception handler in ``main.py``) can surface a real message instead of
mistaking a server failure for "no rows found".
"""
import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("ping.db")

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or ""

# Shared connection pool. httpx.Client is safe to share across the threadpool
# FastAPI uses for sync route handlers.
_TIMEOUT = httpx.Timeout(15.0, connect=10.0)
_client = httpx.Client(timeout=_TIMEOUT)


class DBError(Exception):
    """Raised when the database is unreachable or returns an error response."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DB:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.warning("SUPABASE_URL / SUPABASE_KEY not configured; DB calls will fail")
        self.url = f"{SUPABASE_URL}/rest/v1"
        self.headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }

    def table(self, name: str) -> "Table":
        return Table(self.url, self.headers, name)


class Table:
    def __init__(self, base_url: str, headers: dict, name: str):
        self.url = f"{base_url}/{name}"
        self.name = name
        self.headers = headers
        self.params: dict[str, str] = {}
        self._select = "*"

    # --- query builders (chainable) ---------------------------------------
    def select(self, cols: str = "*") -> "Table":
        self._select = cols
        return self

    def eq(self, col: str, val) -> "Table":
        self.params[col] = f"eq.{val}"
        return self

    def neq(self, col: str, val) -> "Table":
        self.params[col] = f"neq.{val}"
        return self

    def gte(self, col: str, val) -> "Table":
        self.params[col] = f"gte.{val}"
        return self

    def lte(self, col: str, val) -> "Table":
        self.params[col] = f"lte.{val}"
        return self

    def gt(self, col: str, val) -> "Table":
        self.params[col] = f"gt.{val}"
        return self

    def lt(self, col: str, val) -> "Table":
        self.params[col] = f"lt.{val}"
        return self

    def in_(self, col: str, values) -> "Table":
        joined = ",".join(str(v) for v in values)
        self.params[col] = f"in.({joined})"
        return self

    def order(self, col: str, desc: bool = False) -> "Table":
        clause = f"{col}.{'desc' if desc else 'asc'}"
        existing = self.params.get("order")
        self.params["order"] = f"{existing},{clause}" if existing else clause
        return self

    def limit(self, n: int) -> "Table":
        self.params["limit"] = str(n)
        return self

    # --- execution --------------------------------------------------------
    def _request(self, method: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", self.headers)
        try:
            resp = _client.request(method, self.url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            logger.error("DB %s %s failed: %s", method, self.name, exc)
            raise DBError(f"Database unreachable: {exc}") from exc

        if resp.status_code >= 400:
            logger.error(
                "DB %s %s -> %s: %s", method, self.name, resp.status_code, resp.text
            )
            # 4xx is usually a bad request from us; 5xx is the DB. Either way the
            # caller should not treat this as an empty result set.
            raise DBError(
                f"Database error ({resp.status_code}): {resp.text}",
                status_code=502 if resp.status_code >= 500 else 400,
            )
        return resp

    def execute(self) -> dict:
        params = dict(self.params)
        params["select"] = self._select
        resp = self._request("GET", params=params)
        return {"data": resp.json()}

    def insert(self, data) -> dict:
        headers = {**self.headers, "Prefer": "return=representation"}
        payload = data if isinstance(data, list) else [data]
        resp = self._request("POST", json=payload, headers=headers)
        return {"data": resp.json()}

    def update(self, data: dict) -> dict:
        if not self.params:
            # Guard rail: an unfiltered PATCH would rewrite the whole table.
            raise DBError("Refusing to update without a filter", status_code=400)
        headers = {**self.headers, "Prefer": "return=representation"}
        resp = self._request("PATCH", json=data, headers=headers, params=self.params)
        return {"data": resp.json()}

    def delete(self) -> dict:
        if not self.params:
            raise DBError("Refusing to delete without a filter", status_code=400)
        headers = {**self.headers, "Prefer": "return=representation"}
        resp = self._request("DELETE", headers=headers, params=self.params)
        return {"data": resp.json() if resp.text else []}


db = DB()


def get_db() -> DB:
    return db
