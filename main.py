import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, constr
from supabase import create_client, Client
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

app = FastAPI()

# ✅ CORS (ALLOW ALL)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase URL or Key not found")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# -----------------------------
# Input models
# -----------------------------
class CustomerCreate(BaseModel):
    phone: constr(min_length=10, max_length=10)
    full_name: str
    address: str
    password: str
    selected_pack: str
    start_date: date
    total_months: int

class AdminUpdate(BaseModel):
    phone: constr(min_length=10, max_length=10)
    approval_status: str = None
    last_month_paid: date = None

# -----------------------------
# POST endpoint for customer creation
# -----------------------------
@app.post("/create-customer")
def create_customer(customer: CustomerCreate):
    try:
        existing = supabase.table("goldusers").select("phone").eq("phone", customer.phone).execute()
        if existing.data and len(existing.data) > 0:
            raise HTTPException(status_code=400, detail="Phone number already registered")

        supabase.table("goldusers").insert({
            "phone": customer.phone,
            "full_name": customer.full_name,
            "address": customer.address,
            "password": customer.password,
            "selected_pack": customer.selected_pack,
            "start_date": str(customer.start_date),
            "created_at": datetime.now().isoformat(),
            "approval_status": "pending",
            "last_month_paid": None,
            "total_months": customer.total_months,
            "remaining_emi": None
        }).execute()

        return {"message": "Customer created successfully, waiting for admin approval."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------
# PUT endpoint for admin to approve / update last month paid
# -----------------------------
@app.put("/update-customer")
def update_customer(admin_update: AdminUpdate):
    try:
        existing = supabase.table("goldusers").select("*").eq("phone", admin_update.phone).execute()
        if not existing.data or len(existing.data) == 0:
            raise HTTPException(status_code=404, detail="Customer not found")

        customer = existing.data[0]
        update_data = {}

        if admin_update.approval_status:
            update_data["approval_status"] = admin_update.approval_status

        if admin_update.last_month_paid:
            update_data["last_month_paid"] = str(admin_update.last_month_paid)
            start_date = datetime.strptime(customer["start_date"], "%Y-%m-%d").date()
            months_paid = relativedelta(admin_update.last_month_paid, start_date).months + \
                          (relativedelta(admin_update.last_month_paid, start_date).years * 12) + 1
            remaining = max(customer["total_months"] - months_paid, 0)
            update_data["remaining_emi"] = remaining

        supabase.table("goldusers").update(update_data).eq("phone", admin_update.phone).execute()

        return {"message": "Customer updated successfully", "updated_fields": update_data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------
# GET endpoint for customer details
# -----------------------------
@app.get("/get-customer/{phone}")
def get_customer(phone: str):
    try:
        existing = supabase.table("goldusers").select("*").eq("phone", phone).execute()
        if not existing.data or len(existing.data) == 0:
            raise HTTPException(status_code=404, detail="Customer not found")

        customer = existing.data[0]
        start_date = datetime.strptime(customer["start_date"], "%Y-%m-%d").date()
        end_date = start_date + relativedelta(months=customer["total_months"])

        return {
            "phone": customer["phone"],
            "full_name": customer["full_name"],
            "address": customer["address"],
            "selected_pack": customer["selected_pack"],
            "start_date": customer["start_date"],
            "last_month_paid": customer["last_month_paid"],
            "remaining_emi": customer["remaining_emi"],
            "end_date": str(end_date),
            "approval_status": customer["approval_status"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/customers")
def get_all_customers():
    try:
        response = supabase.table("goldusers").select(
            "phone, full_name, approval_status, last_month_paid, remaining_emi"
        ).execute()

        return response.data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/customers/all")
def get_all_customers_full():
    try:
        response = supabase.table("goldusers").select("*").execute()
        return response.data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
