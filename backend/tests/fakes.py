"""An in-memory stand-in for the Supabase REST client, for tests."""
from collections import defaultdict


class FakeTable:
    def __init__(self, store, name):
        self.store = store
        self.name = name
        self.filters = []

    def select(self, cols="*"):
        return self

    def eq(self, col, val):
        self.filters.append((col, val))
        return self

    def neq(self, col, val):
        return self

    def order(self, col, desc=False):
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
        return True

    def execute(self):
        return {"data": [r for r in self.store[self.name] if self._match(r)]}

    def insert(self, data):
        items = data if isinstance(data, list) else [data]
        out = []
        for item in items:
            item = dict(item)
            item.setdefault("id", f"{self.name}-{len(self.store[self.name]) + 1}")
            self.store[self.name].append(item)
            out.append(item)
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
