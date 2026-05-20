import os
from dotenv import load_dotenv
import httpx

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL").rstrip('/')
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

class DB:
    def __init__(self):
        self.url = f"{SUPABASE_URL}/rest/v1"
        self.headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
    
    def table(self, name):
        return Table(self.url, self.headers, name)

class Table:
    def __init__(self, base_url, headers, name):
        self.url = f"{base_url}/{name}"
        self.headers = headers
        self.query_params = {}
    
    def select(self, cols="*"):
        return self
    
    def eq(self, col, val):
        self.query_params[col] = f"eq.{val}"
        return self
    
    def execute(self):
        try:
            response = httpx.get(self.url, params=self.query_params, headers=self.headers)
            return {"data": response.json() if response.status_code == 200 else []}
        except:
            return {"data": []}
    
    def insert(self, data):
        try:
            headers = self.headers.copy()
            headers["Prefer"] = "return=representation"
            response = httpx.post(self.url, json=[data], headers=headers)
            return {"data": response.json() if response.status_code in [200, 201] else []}
        except Exception as e:
            return {"data": []}
    def update(self, data):
        try:
            headers = self.headers.copy()
            headers["Prefer"] = "return=representation"
            response = httpx.patch(self.url, json=data, headers=headers, params=self.query_params)
            if response.status_code in [200, 201]:
                return {"data": response.json()}
            return {"data": []}
        except Exception as e:
            return {"data": []}

db = DB()

def get_db():
    return db