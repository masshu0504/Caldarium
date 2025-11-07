<<<<<<< Updated upstream

import os
import json
from openai import OpenAI
import pdfplumber

import auditsAndRecord

with open("apikey.txt", "r", encoding="utf-8") as f:
    API_KEY = f.read().strip()


PDF_DIR = "input_invoices"
OUTPUT_DIR = "output_invoices"
OUTPUT_AUDIT_FILE = "output_audit.txt"
# store parsed filenames as a JSON array


MODEL_NAME = "openai/gpt-4.1"
TEMPERATURE = 0.4

invoice_formatting = "{title:Invoice,type:object,properties:{invoice_number:{type:string},patient_id:{type:string,},invoice_date:{type:string.format:mm-dd-yyyy,description:Date invoicewas issued},due_date:{type:string,format:mm-dd-yyyy},patient_name:{type:string},patient_age:{type:number},patient_address:{type:string,description:Patient mailing address NOT hospital address},patient_phone:{type:string,format:x-xxx-xxx-xxxx,description:Patient phone number NOT HOSPITAL PHONE},patient_email:{type:string,description:Patient email address NOT EMAIL OF HOSPITAL},admission_date:{type:string,format:mm-dd-yyyy},discharge_date:{type:string,format:mm-dd-yyyy},subtotal_amount:{type:number,minimum:0},discount_amount:{type:number,minimum:0},total_amount:{type:number,minimum:0},provider_name:{type:string,description:Name of the Doctor NOT THE NAME OF THE HOSPITAL},bed_id:{type:string},line_items:{type:array,description:List ofindividual line items on the invoice,items:{type:object,properties:{description:{type:string},code:{type:string},amount:{type:number,minimum:0}}}}}}"


def is_parsed_file(filename: str) -> bool:
    basename = os.path.splitext(filename)[0]
    expected = os.path.join(OUTPUT_DIR, f"{basename}.json")
    return os.path.isfile(expected)



def liteBot(messages, temperature=TEMPERATURE):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=API_KEY
    )

    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=temperature
    )
    return completion.choices[0].message.content.strip()


# ------------------------
# MAIN EXECUTION
# ------------------------

for filename in os.listdir(PDF_DIR):
    if not filename.lower().endswith(".pdf") or is_parsed_file(filename):
        continue

    pdf_path = os.path.join(PDF_DIR, filename)
    print(f"Processing {filename}...")
    
    with pdfplumber.open(pdf_path) as pdf:
        # Use layout-aware text extraction for better column handling
        pages_text = [
            page.extract_text(x_tolerance=2, y_tolerance=2) or "" 
            for page in pdf.pages
        ]
    full_text = "\n\n".join(pages_text).strip()



    system_prompt = "You are performing NER labeling on invoices. Extract the following fields in strict JSON format (no text outside JSON): " + invoice_formatting +". If a field is missing, set it to null. Use Common Sense when filling fields, for example info@whitepetalhospital.org would NOT be the patient email as it is clearly a hospital email."
    

    system = [{"role": "system", "content": system_prompt}]
    user = [{"role": "user", "content": full_text}]

    try:
        outputJsonString = liteBot(system + user, TEMPERATURE)
    except Exception as e:
        print(f"Error calling model for {filename}: {e}")
        continue

    cleaned = (
        outputJsonString.strip()
        .removeprefix("```json")
        .removesuffix("```")
        .strip()
    )

    try:
        parsed = json.loads(cleaned)
    
    except json.JSONDecodeError as e:
        print(f"Invalid JSON for {filename}: {e}")
        print("Raw output:\n", outputJsonString[:300], "...\n")
        continue

    if isinstance(parsed, list) and len(parsed) == 1:
        invoice_data = parsed[0]
    else:
        invoice_data = parsed

    # Analyze fields
    fields_filled = [k for k, v in invoice_data.items() if v not in (None, "", [], {})]
    fields_null = [k for k, v in invoice_data.items() if v in (None, "", [], {})]
    

    # Save output
    output_filename = os.path.join(OUTPUT_DIR, f"{os.path.splitext(filename)[0]}.json")
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(invoice_data, f, indent=2, ensure_ascii=False)

    print(f"Saved {output_filename}")

    # Audit entry
    auditsAndRecord.log_audit(filename, fields_filled, fields_null, system_prompt,outputJsonString)

    # Record parsed files as a JSON array (creates file if missing)
   
=======



API_KEY ="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"

import os
import json
import pdfplumber
from datetime import datetime
from openai import OpenAI

PDF_DIR = "input_invoices"
OUTPUT_DIR = "output_invoices"
OUTPUT_AUDIT_FILE = "output_audit.txt"
os.makedirs(OUTPUT_DIR, exist_ok=True)

MODEL_NAME = "google/gemma-3-4b-it"
TEMPERATURE = 0.5

invoice_formatting = (
    "invoice_number: null, patient_id: null, invoice_date: null, due_date: null, "
    "patient_name: null, patient_age: null, patient_address: null, patient_phone: null, "
    "patient_email: null, admission_date: null, discharge_date: null, subtotal_amount: null, "
    "discount_amount: null, total_amount: null, provider_name: null, bed_id: null, "
    "line_items: [ { description: null, code: null, amount: null } ]"
)


def liteBot(messages, temperature=TEMPERATURE):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=API_KEY
    )

    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=temperature
    )

    return completion.choices[0].message.content.strip()


def log_audit(filename, fields_filled, fields_null, system_prompt):
    """Append an audit record to the audit log."""
    with open(OUTPUT_AUDIT_FILE, "a", encoding="utf-8") as audit:
        audit.write("\n" + "=" * 60 + "\n")
        audit.write(f"File: {filename}\n")
        audit.write(f"Timestamp: {datetime.now().isoformat(timespec='seconds')}\n")
        audit.write(f"Model: {MODEL_NAME}\n")
        audit.write(f"Temperature: {TEMPERATURE}\n")
        audit.write(f"System Prompt:\n{system_prompt}\n")
        audit.write(f"Fields auto-filled ({len(fields_filled)}): {', '.join(fields_filled)}\n")
        audit.write(f"Fields left blank ({len(fields_null)}): {', '.join(fields_null)}\n")
        audit.write("=" * 60 + "\n\n")


# ------------------------
# MAIN EXECUTION
# ------------------------
for filename in os.listdir(PDF_DIR):
    if not filename.lower().endswith(".pdf"):
        continue

    pdf_path = os.path.join(PDF_DIR, filename)
    print(f"📄 Processing {filename}...")

    with pdfplumber.open(pdf_path) as pdf:
        pages_text = [page.extract_text() or "" for page in pdf.pages]
    full_text = "\n\n".join(pages_text).strip()

    system_prompt = (
        "You are performing NER labeling on invoices. Extract the following fields "
        "in strict JSON format (no text outside JSON): " + invoice_formatting +
        ". If a field is missing, set it to null. The 'Provider Name' is the name of the Doctor and not the hospital."
    )

    system = [{"role": "system", "content": system_prompt}]
    user = [{"role": "user", "content": full_text}]

    try:
        outputJsonString = liteBot(system + user, TEMPERATURE)
    except Exception as e:
        print(f"Error calling model for {filename}: {e}")
        continue

    cleaned = (
        outputJsonString.strip()
        .removeprefix("```json")
        .removesuffix("```")
        .strip()
    )

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON for {filename}: {e}")
        print("Raw output:\n", outputJsonString[:300], "...\n")
        continue

    if isinstance(parsed, list) and len(parsed) == 1:
        invoice_data = parsed[0]
    else:
        invoice_data = parsed

    # Analyze fields
    fields_filled = [k for k, v in invoice_data.items() if v not in (None, "", [], {})]
    fields_null = [k for k, v in invoice_data.items() if v in (None, "", [], {})]

    # Save output
    output_filename = os.path.join(OUTPUT_DIR, f"invoice_{os.path.splitext(filename)[0]}.json")
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(invoice_data, f, indent=2, ensure_ascii=False)

    print(f"Saved {output_filename}")

    # Audit entry
    log_audit(filename, fields_filled, fields_null, system_prompt)
>>>>>>> Stashed changes
