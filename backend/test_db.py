from services.database import get_db

db = get_db()
response = db.table("salons").select("*").execute()
print("Connection successful!")
print(response.data)