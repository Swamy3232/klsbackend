import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, constr
from supabase import create_client, Client
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import os
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()
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

class PaymentCreate(BaseModel):
    phone: str = Field(..., example="9876543210")      # Link to goldusers
    paid_amount: float = Field(..., example=5000.00)
    utr_number: str = Field(..., example="UTR123456789")

# -----------------------------
# Input models
# -----------------------------
class CustomerCreate(BaseModel):
    phone: constr(min_length=10, max_length=10) # type: ignore
    full_name: str
    address: str
    password: str
    # selected_pack: str
    start_date: date
    total_months: int

class AdminUpdate(BaseModel):
    phone: str
    approval_status: str  # should be "approved" or "rejected"

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
           
            "start_date": str(customer.start_date),
            "created_at": datetime.now().isoformat(),
            "approval_status": "pending",
            
            "total_months": customer.total_months,
           
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
        # Check if customer exists
        existing = supabase.table("goldusers").select("phone").eq("phone", admin_update.phone).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Customer not found")

        # Update only approval_status
        supabase.table("goldusers") \
            .update({"approval_status": admin_update.approval_status}) \
            .eq("phone", admin_update.phone) \
            .execute()

        return {
            "message": f"Customer {admin_update.phone} has been {admin_update.approval_status} successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# -----------------------------
# GET endpoint for customer details
# -----------------------------
# @app.get("/get-customer/{phone}")
# def get_customer(phone: str):
#     try:
#         existing = supabase.table("goldusers").select("*").eq("phone", phone).execute()
#         if not existing.data or len(existing.data) == 0:
#             raise HTTPException(status_code=404, detail="Customer not found")

#         customer = existing.data[0]
#         start_date = datetime.strptime(customer["start_date"], "%Y-%m-%d").date()
#         end_date = start_date + relativedelta(months=customer["total_months"])

#         return {
#             "phone": customer["phone"],
#             "full_name": customer["full_name"],
#             "address": customer["address"],
#             "selected_pack": customer["selected_pack"],
#             "start_date": customer["start_date"],
#             "last_month_paid": customer["last_month_paid"],
#             "remaining_emi": customer["remaining_emi"],
#             "end_date": str(end_date),
#             "approval_status": customer["approval_status"]
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
@app.get("/customers")
def get_all_customers():
    try:
        response = supabase.table("goldusers").select(
            "phone, full_name, approval_status, created_at"
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
class PaymentCreate(BaseModel):
    phone: str = Field(..., example="9876543210")      # User's phone number
    paid_amount: float = Field(..., example=5000.00)
    utr_number: str = Field(..., example="UTR123456789")

# ------------------------------
# POST endpoint to add payment
# ------------------------------
@app.post("/create-payment")
def create_payment(payment: PaymentCreate):
    try:
        # Fetch user name from goldusers using phone
        existing_user = supabase.table("goldusers").select("full_name").eq("phone", payment.phone).execute()
        
        if not existing_user.data or len(existing_user.data) == 0:
            raise HTTPException(status_code=404, detail="User not found in goldusers")

        # Get the user's name
        user_name = existing_user.data[0]["full_name"]

        # Insert payment into payments table with created_at
        supabase.table("payments").insert({
            "phone": payment.phone,
            "name": user_name,           # Auto-filled from goldusers
            "paid_amount": payment.paid_amount,
            "utr_number": payment.utr_number,
            "payment_date": datetime.now().isoformat(),
            "approval_status": "pending",
            "created_at": datetime.now().isoformat()  # <-- new column
        }).execute()

        return {"message": f"Payment for {user_name} submitted successfully, pending admin approval."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
class PaymentSummaryResponse(BaseModel):
    phone: str
    full_name: str
    total_months: int
    payments_count: int
    total_paid: float
    remaining_months: int
    payment_dates: list = []  # List of all payment dates

@app.get("/gold_user_summary/{phone}", response_model=PaymentSummaryResponse)
def get_payment_summary(phone: str):
    try:
        # Fetch user from goldusers
        user = supabase.table("goldusers").select("*").eq("phone", phone).execute()
        if not user.data or len(user.data) == 0:
            raise HTTPException(status_code=404, detail="User not found in goldusers")
        
        user_data = user.data[0]
        full_name = user_data["full_name"]
        total_months = user_data.get("total_months", 0)
        
        # Fetch all payments for this user
        payments = supabase.table("payments").select("*").eq("phone", phone).execute()
        payments_count = len(payments.data) if payments.data else 0
        total_paid = sum(p.get("paid_amount", 0) for p in payments.data) if payments.data else 0
        
        remaining_months = max(total_months - payments_count, 0)
        
        return PaymentSummaryResponse(
            phone=phone,
            full_name=full_name,
            total_months=total_months,
            payments_count=payments_count,
            total_paid=total_paid,
            remaining_months=remaining_months
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/gold_users_summary", response_model=list[PaymentSummaryResponse])
def get_all_users_payment_summary():
    try:
        # Fetch all gold users
        users = supabase.table("goldusers").select("*").execute()
        if not users.data:
            raise HTTPException(status_code=404, detail="No gold users found")

        result = []

        for user in users.data:
            phone = user["phone"]
            full_name = user["full_name"]
            total_months = user.get("total_months", 0)

            # Fetch ONLY approved payments for this user
            payments = (
                supabase.table("payments")
                .select("paid_amount, created_at")
                .eq("phone", phone)
                .eq("approval_status", "approved")
                .order("created_at", desc=True)
                .execute()
            )

            approved_count = len(payments.data) if payments.data else 0
            total_paid = sum(p.get("paid_amount", 0) for p in payments.data) if payments.data else 0
            remaining_months = max(total_months - approved_count, 0)

            result.append(PaymentSummaryResponse(
                phone=phone,
                full_name=full_name,
                total_months=total_months,
                payments_count=approved_count,   # EMI count
                total_paid=total_paid,           # Only approved amount
                remaining_months=remaining_months
            ))

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/gold_user_summary_auth", response_model=PaymentSummaryResponse)
def get_user_payment_summary_auth(phone: str, password: str):
    try:
        # Validate user with phone and password
        user = supabase.table("goldusers").select("*").eq("phone", phone).execute()
        
        if not user.data or len(user.data) == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user.data[0]
        
        # Verify password
        if user_data.get("password") != password:
            raise HTTPException(status_code=401, detail="Invalid phone or password")
        
        full_name = user_data["full_name"]
        total_months = user_data.get("total_months", 0)
        
        # Fetch ONLY approved payments for this user
        payments = (
            supabase.table("payments")
            .select("paid_amount, created_at, payment_date")
            .eq("phone", phone)
            .eq("approval_status", "approved")
            .order("created_at", desc=True)
            .execute()
        )
        
        approved_count = len(payments.data) if payments.data else 0
        total_paid = sum(p.get("paid_amount", 0) for p in payments.data) if payments.data else 0
        remaining_months = max(total_months - approved_count, 0)
        
        payment_dates = [p.get("payment_date") for p in payments.data] if payments.data else []
        
        return PaymentSummaryResponse(
            phone=phone,
            full_name=full_name,
            total_months=total_months,
            payments_count=approved_count,
            total_paid=total_paid,
            remaining_months=remaining_months,
            payment_dates=payment_dates
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PaymentUpdateByCreatedAt(BaseModel):
    phone: str
    created_at: datetime   # exact timestamp of the payment
    approval_status: str   # approved / rejected / pending
@app.put("/update-payment")
def update_payment(update: PaymentUpdateByCreatedAt):
    try:
        # Update directly using phone + created_at
        result = (
            supabase.table("payments")
            .update({"approval_status": update.approval_status})
            .eq("phone", update.phone)
            .eq("created_at", update.created_at.isoformat())
            .execute()
        )

        # Supabase returns empty list if nothing updated
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Payment not found for given phone and created_at"
            )

        return {
            "message": "Payment updated successfully",
            "phone": update.phone,
            "created_at": update.created_at,
            "approval_status": update.approval_status
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/payments")
def get_all_payments():
    try:
        payments = supabase.table("payments").select("*").order("payment_date", desc=True).execute()
        return payments.data  # List of all payments
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))