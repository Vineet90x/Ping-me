from fastapi import APIRouter, HTTPException
from models.invoice import InvoiceCreate, InvoiceResponse
from services.database import get_db
import urllib.parse

router = APIRouter()

@router.post("/{salon_id}/invoices", response_model=InvoiceResponse)
def create_invoice(salon_id: str, invoice: InvoiceCreate):
    db = get_db()
    
    # Check salon exists
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    
    salon = salon_response["data"][0]
    
    # Check customer exists
    customer_response = db.table("customers").eq("id", invoice.customer_id).execute()
    if not customer_response["data"]:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    customer = customer_response["data"][0]
    
    # Create invoice
    response = db.table("invoices").insert({
        "salon_id": salon_id,
        "customer_id": invoice.customer_id,
        "amount": invoice.amount,
        "description": invoice.description,
        "payment_status": "unpaid"
    })
    
    if not response["data"]:
        raise HTTPException(status_code=400, detail="Insert failed")
    
    invoice_data = response["data"][0]
    invoice_id = invoice_data["id"]
    
    # Generate UPI link
    amount_rupees = round(invoice.amount, 2)
    upi_id = salon["upi_id"]
    
    if upi_id:
        upi_link = f"upi://pay?pa={upi_id}&pn=Ping&am={amount_rupees}&tr=INV-{invoice_id[:8]}"
    else:
        upi_link = None
    
    return {
        "id": invoice_id,
        "salon_id": salon_id,
        "customer_id": invoice.customer_id,
        "amount": invoice.amount,
        "description": invoice.description,
        "payment_status": "unpaid",
        "pdf_url": None,
        "upi_link": upi_link
    }

@router.get("/{salon_id}/invoices")
def list_invoices(salon_id: str, status: str = None):
    db = get_db()
    
    salon_response = db.table("salons").eq("id", salon_id).execute()
    if not salon_response["data"]:
        raise HTTPException(status_code=404, detail="Salon not found")
    
    response = db.table("invoices").eq("salon_id", salon_id).execute()
    invoices = response["data"] if response["data"] else []
    
    if status:
        invoices = [inv for inv in invoices if inv["payment_status"] == status]
    
    return invoices

@router.patch("/{salon_id}/invoices/{invoice_id}")
def update_invoice_status(salon_id: str, invoice_id: str, payment_status: str):
    db = get_db()
    
    if payment_status not in ["unpaid", "paid"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    response = db.table("invoices").eq("id", invoice_id).execute()
    if not response["data"]:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    from datetime import datetime
    update_data = {"payment_status": payment_status}
    if payment_status == "paid":
        update_data["paid_at"] = datetime.now().isoformat()
    
    db.table("invoices").eq("id", invoice_id).update(update_data)
    
    return {"message": "Invoice updated", "payment_status": payment_status}