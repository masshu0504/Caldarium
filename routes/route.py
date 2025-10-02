from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import psycopg2
from datetime import datetime

import os
from pathlib import Path
from dotenv import load_dotenv


env_path = Path('.') / '.env.example'

load_dotenv(dotenv_path=env_path)

DATABASE_URL = os.getenv("DATABASE_URL")

routes = APIRouter()

@routes.get("/health")
async def health():
    return {"status": "OK"}


@routes.get("/ready")
async def ready():
    try:
        
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT"),
            dbname=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD")
        )
        cur = conn.cursor()
        cur.execute("SELECT 1;")  # simple query
        result = cur.fetchone()
        cur.close()
        conn.close()
        if result == (1,):
            return {"status": "DB connection OK"}
        else:
            return {"status": "DB connection failed"}
    except Exception as e:
        return {"status": f"DB connection failed", "error": str(e)}
    
@routes.get("/v1/parse")
async def parse(file: UploadFile = File(...)):
    filename = file.filename
    content_type = file.content_type

    # uses parser*
    contents = await file.read()
    size = len(contents)
    # change after getting parser
    
    """
    invoice_number = contents.get("invoice_number")
    patient_id = contents.get("patiend_id")
    subtotal_amount = contents.get("subtotal_amount")
    invoice_date = contents.get("invoice_date")
    total_amount = contents.get("total_amount")
    line_items = contents.get("line_items")

    due_date = contents.get("due_date")
    patient_name = contents.get("patient_name")
    patient_age = contents.get("patient_age")
    patient_address = contents.get("patient_address")
    patient_phone = contents.get("patient_phone")
    patient_email = contents.get("patient_email")
    admission_date = contents.get("admission_date")
    discharge_date = contents.get("discharge_date")
    discount_amount = contents.get("discount_amount")
    provider_name = contents.get("provider_name")
    provider_email = contents.get("provider_email")
    provider_website = contents.get("provider_website")
    account_no = contents.get("account_no")
    hospital_no = contents.get("hospital_no")
    bed_no = contents.get("bed_no")
    consultant = contents.get("consultant")
    billed_to_address = contents.get("billed_to_address")
    tax_rate = contents.get("tax_rate")
    tax_amount = contents.get("tax_amount")
    currency = contents.get("currency")
    payment_instructions = contents.get("payment_instructions")
    disclaimer = contents.get("disclaimer")
    """
    invoice_number = 0
    patient_id = 0
    subtotal_amount = 0
    invoice_date = 0
    total_amount = 0
    line_items = 0

    due_date = 0
    patient_name = 0
    patient_age = 0
    patient_address = 0
    patient_phone = 0
    patient_email = 0
    admission_date = 0
    discharge_date = 0
    discount_amount = 0
    provider_name = 0
    provider_email = 0
    provider_website = 0
    account_no = 0
    hospital_no = 0
    bed_no = 0
    consultant = 0
    billed_to_address = 0
    tax_rate = 0
    tax_amount = 0
    currency = 0
    payment_instructions = 0
    disclaimer = 0

    if invoice_number is None or patient_id is None or subtotal_amount is None or invoice_date is None or total_amount is None or line_items is None:
        return JSONResponse(
            status_code=422,
            content={
                "status" : "failed to extract all required fields", 
                "error": 422
            }
        )
        
    else:
        time = datetime.utcnow()

        return {
            "invoice_number": invoice_number,
            "patient_id": patient_id,
            "subtotal_amount": subtotal_amount,
            "invoice_date": invoice_date,
            "total_amount": total_amount,
            "line_items": line_items,
            "due_date": due_date,
            "patient_name": patient_name,
            "patient_age": patient_age,
            "patient_address": patient_address,
            "patient_phone": patient_phone,
            "patient_email": patient_email,
            "admission_date": admission_date,
            "discharge_date": discharge_date,
            "discount_amount": discount_amount,
            "provider_name": provider_name,
            "provider_email": provider_email,
            "provider_website": provider_website,
            "account_no": account_no,
            "hospital_no": hospital_no,
            "bed_no": bed_no,
            "consultant": consultant,
            "billed_to_address": billed_to_address,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "currency": currency,
            "payment_instructions": payment_instructions,
            "disclaimer": disclaimer
        }


