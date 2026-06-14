"""Manual DB connectivity check. Run directly: `python test_db.py`.

(Not a pytest test — the automated suite lives in ./tests.)
"""
from services.database import get_db


def main():
    db = get_db()
    response = db.table("salons").select("*").limit(5).execute()
    print("Connection successful!")
    print(f"Found {len(response['data'])} salon(s):")
    for salon in response["data"]:
        print(f"  - {salon.get('salon_name')} ({salon.get('owner_phone')})")


if __name__ == "__main__":
    main()
