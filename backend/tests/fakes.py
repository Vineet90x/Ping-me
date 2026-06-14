"""An in-memory stand-in for the Supabase REST client, for tests."""
from collections import defaultdict


class FakeTable:
    def __init__(self, store, name):
        self.store = store
        self.name = name
        self.filters = []
        self.in_filters = []
        self._order = None

    def select(self, cols="*"):
        return self

    def eq(self, col, val):
        self.filters.append((col, val))
        return self

    def neq(self, col, val):
        return self

    def in_(self, col, values):
        self.in_filters.append((col, [str(v) for v in values]))
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, n):
        return self

    def _match(self, row):
        for col, val in self.filters:
            rv = row.get(col)
            if isinstance(rv, bool):
                if str(rv).lower() != str(val).lower():
                    return False
            elif str(rv) != str(val):
                return False
        for col, values in self.in_filters:
            if str(row.get(col)) not in values:
                return False
        return True

    def execute(self):
        rows = [r for r in self.store[self.name] if self._match(r)]
        if self._order:
            col, desc = self._order
            rows = sorted(rows, key=lambda r: r.get(col) or "", reverse=desc)
        return {"data": rows}

    def insert(self, data):
        items = data if isinstance(data, list) else [data]
        out = []
        for item in items:
            item = dict(item)
            item.setdefault("id", f"{self.name}-{len(self.store[self.name]) + 1}")
            self.store[self.name].append(item)
            out.append(item)
        return {"data": out}

    def upsert(self, data, on_conflict, ignore_duplicates=False):
        keys = [k.strip() for k in on_conflict.split(",")]
        items = data if isinstance(data, list) else [data]
        out = []
        for item in items:
            existing = next(
                (r for r in self.store[self.name] if all(str(r.get(k)) == str(item.get(k)) for k in keys)),
                None,
            )
            if existing is not None:
                if ignore_duplicates:
                    continue  # left untouched and NOT returned
                existing.update(item)
                out.append(existing)
            else:
                out.append(self.insert(item)["data"][0])
        return {"data": out}

    def update(self, data):
        updated = []
        for row in self.store[self.name]:
            if self._match(row):
                row.update(data)
                updated.append(row)
        return {"data": updated}

    def delete(self):
        kept, removed = [], []
        for row in self.store[self.name]:
            (removed if self._match(row) else kept).append(row)
        self.store[self.name] = kept
        return {"data": removed}


class FakeDB:
    def __init__(self):
        self.store = defaultdict(list)

    def table(self, name):
        self.store.setdefault(name, [])
        return FakeTable(self.store, name)


class FakeSession:
    """In-memory stand-in for services.session.Session (no Redis)."""

    def __init__(self):
        self.data = None

    def get(self):
        return dict(self.data) if self.data is not None else None

    def set(self, data, ttl=None):
        self.data = dict(data)

    def update(self, data):
        current = self.data or {}
        current.update(data)
        self.data = current

    def delete(self):
        self.data = None

    def exists(self):
        return self.data is not None
