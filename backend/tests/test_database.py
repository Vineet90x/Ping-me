"""Regression tests for the Supabase REST client's request plumbing."""
from services import database


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="[]"):
        self.status_code = status_code
        self._payload = payload if payload is not None else [{"id": "row-1"}]
        self.text = text

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self):
        self.calls = []

    def request(self, method, url, **kwargs):
        # Records the call; would raise TypeError if `headers` were passed twice.
        self.calls.append((method, kwargs))
        return FakeResponse()


def test_write_methods_send_headers_exactly_once(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(database, "_client", fake)
    db = database.DB()

    db.table("salons").insert({"owner_name": "Neha"})
    db.table("salons").eq("id", "1").update({"owner_name": "Neha2"})
    db.table("salons").eq("id", "1").delete()

    methods = [m for m, _ in fake.calls]
    assert methods == ["POST", "PATCH", "DELETE"]
    for _, kwargs in fake.calls:
        # The bug was a duplicate `headers` kwarg raising TypeError before we got here.
        assert "headers" in kwargs
        assert kwargs["headers"].get("Prefer") == "return=representation"


def test_insert_wraps_single_dict_in_list(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(database, "_client", fake)
    database.DB().table("services").insert({"service_name": "Haircut"})
    _, kwargs = fake.calls[0]
    assert kwargs["json"] == [{"service_name": "Haircut"}]
