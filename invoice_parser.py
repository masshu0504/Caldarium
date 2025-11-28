# -*- coding: utf-8 -*-
"""invoice_parser.ipynb"""

import os
import pdfplumber
import shutil
import re
import json
import uuid
from parser_audit_logger import AuditLogger, iso_yyyymmdd
from template_detector import (
    detect_template_signature,
    classify_template,
    log_template_detection,
)

# -----------------------------
# PATHS / FOLDERS
# -----------------------------
pdf_folder = "medical_pdfs/invoices"
parsed_texts_folder = "parsed_texts"
json_output_folder = "json_invoices"
AUDIT_LOG_PATH = "logs/invoice_audit.jsonl"

# store layout detection results here (keyed by doc_id)
template_detection_results = {}

# -----------------------------
# RESET FOLDERS ON START
# -----------------------------
# Reset parsed_texts
if os.path.exists(parsed_texts_folder):
    shutil.rmtree(parsed_texts_folder)
os.makedirs(parsed_texts_folder, exist_ok=True)

# Reset json_invoices
if os.path.exists(json_output_folder):
    shutil.rmtree(json_output_folder)
os.makedirs(json_output_folder, exist_ok=True)

print("🧹 Reset parsed_texts and json_invoices folders. Starting fresh...\n")

# -----------------------------
# STEP 1: PDF → TEXT
# -----------------------------
for filename in os.listdir(pdf_folder):
    if filename.lower().endswith(".pdf"):
        pdf_path = os.path.join(pdf_folder, filename)

        # -------------------------------
        # TEMPLATE DETECTION
        # -------------------------------
        detection_run_id = str(uuid.uuid4())  # separate from invoice parsing run_id
        doc_id = os.path.splitext(filename)[0]

        sig = detect_template_signature(pdf_path)
        template_id, score, unforeseen = classify_template(sig)
        log_template_detection(detection_run_id, doc_id, template_id, score, unforeseen)

        # save for later use in TXT → JSON phase
        template_detection_results[doc_id] = {
            "template_id": template_id,
            "score": score,
            "is_unforeseen": unforeseen,
        }

        # PDF → text extraction
        output_path = os.path.join(parsed_texts_folder, f"{doc_id}.txt")
        print(f"Parsing {filename}...")

        with pdfplumber.open(pdf_path) as pdf:
            all_text = ""
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                all_text += f"\n--- Page {i+1} ---\n{text}\n"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(all_text)

        print(f"✅ Saved parsed text to {output_path}\n")

print("All PDFs parsed.\n")

# -----------------------------
# CONFIG FOR JSON PARSING
# -----------------------------
SCHEMA_VERSION = "invoice_v1_reset"
PARSER_VERSION = "rules-0.3"

invoice_logger = AuditLogger(
    actor="minna_d",
    role="parser",
    schema_version=SCHEMA_VERSION,
    parser_version=PARSER_VERSION,
    log_path=AUDIT_LOG_PATH,
)

input_folder = parsed_texts_folder
output_folder = json_output_folder


# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def extract_amount(value):
    """Convert strings like '$123.45' to float"""
    try:
        return float(re.sub(r"[^0-9.]", "", value))
    except Exception:
        return None


def base_schema():
    """Consistent invoice schema for all templates, with optional fields set to None"""
    return {
        "invoice_number": None,
        "patient_id": None,
        "invoice_date": None,
        "due_date": None,
        "patient_name": None,
        "patient_age": None,
        "patient_address": None,
        "patient_phone": None,
        "patient_email": None,
        "admission_date": None,
        "discharge_date": None,
        "subtotal_amount": None,
        "discount_amount": None,
        "total_amount": None,
        "provider_name": None,
        "bed_id": None,
        "line_items": []
    }


def _count_non_null(d: dict) -> int:
    """Counts the number of non-null, non-empty values in a dictionary."""
    return sum(v not in (None, "", []) for v in d.values())


def remove_nulls(obj):
    """
    Recursively remove keys with value None from dicts.
    Keeps empty strings and empty lists (only strips actual JSON nulls).
    """
    if isinstance(obj, dict):
        return {k: remove_nulls(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [remove_nulls(v) for v in obj]
    else:
        return obj


# -----------------------------
# TEMPLATE PARSERS
# -----------------------------
def _parse_money_line_exact(text, label):
    pattern = rf"(?m)^\s*{re.escape(label)}\s*\$?([\d,]+\.\d{{2}})\s*$"
    m = re.search(pattern, text, re.IGNORECASE)
    return float(m.group(1).replace(",", "")) if m else None


def _find_last_amount_line(text):
    pattern = r"(?m)^\s*Total(?:\s*[:])?\s*\$?([\d,]+\.\d{2})\s*$"
    matches = re.findall(pattern, text, re.IGNORECASE)
    return float(matches[-1].replace(",", "")) if matches else None


def parse_hot_springs(text: str, run_id: str, doc_id: str, logger: AuditLogger) -> dict:
    invoice = base_schema()  # start with consistent schema

    # Provider (doctor names)
    provider_match = re.findall(r"Dr\.\s+[A-Z][a-zA-Z'-]+\s+[A-Z][a-zA-Z'-]+", text)
    if provider_match:
        invoice["provider_name"] = ", ".join(provider_match)
        logger.auto_extract_parser(run_id, doc_id, "provider_name", invoice["provider_name"], status="success")
    else:
        invoice["provider_name"] = "Hot Springs General Hospital"
        logger.auto_extract_parser(run_id, doc_id, "provider_name", invoice["provider_name"], status="success")

    # Invoice/date/patient ID
    inv_line = re.search(r"Invoice #\s*(\S+)\s*Date:\s*([\d-]+)\s+([\d-]+)\s+(\S+)", text)
    if inv_line:
        invoice["invoice_number"] = inv_line.group(1)
        invoice["invoice_date"] = inv_line.group(2)
        invoice["due_date"] = inv_line.group(3)
        invoice["patient_id"] = inv_line.group(4)
        logger.auto_extract_parser(run_id, doc_id, "invoice_number", invoice["invoice_number"], status="success")
        logger.auto_extract_parser(run_id, doc_id, "invoice_date", invoice["invoice_date"], status="success")
        logger.auto_extract_parser(run_id, doc_id, "due_date", invoice["due_date"], status="success")
        logger.auto_extract_parser(run_id, doc_id, "patient_id", invoice["patient_id"], status="success")

    # Patient details
    name_match = re.search(r"Patient Name:\s*(.+?)\s*Hospital No:", text)
    if name_match:
        invoice["patient_name"] = name_match.group(1).strip()
        logger.auto_extract_parser(run_id, doc_id, "patient_name", invoice["patient_name"], status="success")

    age_match = re.search(r"Patient Age:\s*(\d+)", text)
    if age_match:
        invoice["patient_age"] = int(age_match.group(1))
        logger.auto_extract_parser(run_id, doc_id, "patient_age", invoice["patient_age"], status="success")

    bed_match = re.search(r"Bed No:\s*(\S+)", text)
    if bed_match:
        invoice["bed_id"] = bed_match.group(1)
        logger.auto_extract_parser(run_id, doc_id, "bed_id", invoice["bed_id"], status="success")

    # Patient address (merge split lines)
    addr_match = re.search(
        r"\n([0-9].+)\nAddress:\s*Admission Date:\s*[\d-]+\n([A-Za-z\s]+, [A-Z]{2,} \d{5})",
        text
    )
    if addr_match:
        invoice["patient_address"] = f"{addr_match.group(1).strip()}, {addr_match.group(2).strip()}"
        logger.auto_extract_parser(run_id, doc_id, "patient_address", invoice["patient_address"], status="success")

    # Admission/discharge dates
    ad_match = re.search(r"Admission Date:\s*([\d-]+)", text)
    dc_match = re.search(r"Discharge Date:\s*([\d-]+)", text)
    if ad_match:
        invoice["admission_date"] = ad_match.group(1)
        logger.auto_extract_parser(run_id, doc_id, "admission_date", invoice["admission_date"], status="success")
    if dc_match:
        invoice["discharge_date"] = dc_match.group(1)
        logger.auto_extract_parser(run_id, doc_id, "discharge_date", invoice["discharge_date"], status="success")

    # Financials
    invoice["subtotal_amount"] = _parse_money_line_exact(text, "Sub Total") or _parse_money_line_exact(text, "Subtotal")
    invoice["discount_amount"] = _parse_money_line_exact(text, "Discount")
    invoice["total_amount"] = _find_last_amount_line(text)

    logger.auto_extract_parser(run_id, doc_id, "subtotal_amount", invoice["subtotal_amount"], status="success")
    logger.auto_extract_parser(run_id, doc_id, "discount_amount", invoice["discount_amount"], status="success")
    logger.auto_extract_parser(run_id, doc_id, "total_amount", invoice["total_amount"], status="success")

    # Line items
    line_pattern = re.compile(r"(?m)^\s*([A-Z0-9]{2,})\s+(.+?)\s+\$([\d,]+\.\d{2})\s*$")
    items = []
    for code, desc, amt in line_pattern.findall(text):
        if desc.strip().lower() == "discount":
            continue
        items.append({
            "code": code,
            "description": desc.strip(),
            "amount": float(amt.replace(",", ""))
        })
    invoice["line_items"] = items

    for item in items:
        logger.auto_extract_parser(run_id, doc_id, "line_items", item, status="success")

    return invoice


def parse_rose_petal(text: str, run_id: str, doc_id: str, logger: AuditLogger) -> dict:
    invoice = base_schema()

    # Provider / doctor
    provider_match = re.search(r"(?i)Doctor[:\s]*(Dr\.\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
    invoice["provider_name"] = provider_match.group(1).strip() if provider_match else None
    logger.auto_extract_parser(run_id, doc_id, "provider_name", invoice["provider_name"])

    # Invoice number
    inv_match = re.search(r"Invoice\s*No[:\s]*([A-Z0-9-]+)", text)
    invoice["invoice_number"] = inv_match.group(1).strip() if inv_match else None
    logger.auto_extract_parser(run_id, doc_id, "invoice_number", invoice["invoice_number"])

    # Dates
    due_match = re.search(r"Due\s*Date[:\s]*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
    invoice["due_date"] = due_match.group(1).strip() if due_match else None
    logger.auto_extract_parser(run_id, doc_id, "due_date", invoice["due_date"])

    date_match = re.search(r"(?<!Due\s)Date[:\s]*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
    invoice["invoice_date"] = date_match.group(1).strip() if date_match else None
    logger.auto_extract_parser(run_id, doc_id, "invoice_date", invoice["invoice_date"])

    # Patient name
    lines = text.splitlines()
    patient_name = None
    for i, line in enumerate(lines):
        if "ROSE PETAL CLINIC" in line.upper() and i + 2 < len(lines):
            patient_name = lines[i + 2].strip()
            break
    invoice["patient_name"] = patient_name if patient_name else None
    logger.auto_extract_parser(run_id, doc_id, "patient_name", invoice["patient_name"])

    # Patient contact
    patient_phone_match = re.search(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
    invoice["patient_phone"] = patient_phone_match.group(0).strip() if patient_phone_match else None
    logger.auto_extract_parser(run_id, doc_id, "patient_phone", invoice["patient_phone"])

    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    invoice["patient_email"] = email_match.group(0).strip() if email_match else None
    logger.auto_extract_parser(run_id, doc_id, "patient_email", invoice["patient_email"])

    # Address etc. not present → leave as None in schema

    # Line items
    items_section = re.search(r"Description\s*Code\s*Total(.*?)(?:Subtotal|Sub\s*Total)", text, re.S | re.I)
    items = []
    if items_section:
        for line in items_section.group(1).splitlines():
            m = re.match(r"([A-Za-z\s]+)\s+([A-Z0-9]+)\s*\$?([\d,]+\.\d{2})", line.strip())
            if m:
                desc, code, amt = m.groups()
                items.append({
                    "description": desc.strip(),
                    "code": code.strip(),
                    "amount": float(amt.replace(",", ""))
                })
    invoice["line_items"] = items
    logger.auto_extract_parser(run_id, doc_id, "line_items", len(items))

    # Financials
    subtotal_match = re.search(r"(?:Sub\s?Total|Subtotal)[:\s]*\$?([\d,]+\.\d{2})", text)
    invoice["subtotal_amount"] = float(subtotal_match.group(1).replace(",", "")) if subtotal_match else None
    logger.auto_extract_parser(run_id, doc_id, "subtotal_amount", invoice["subtotal_amount"])

    discount_match = re.search(r"Discount[:\s]*\$?([\d,]+\.\d{2})", text)
    invoice["discount_amount"] = float(discount_match.group(1).replace(",", "")) if discount_match else None
    logger.auto_extract_parser(run_id, doc_id, "discount_amount", invoice["discount_amount"])

    total_match = re.findall(r"Total[:\s]*\$?([\d,]+\.\d{2})", text)
    invoice["total_amount"] = float(total_match[-1].replace(",", "")) if total_match else None
    logger.auto_extract_parser(run_id, doc_id, "total_amount", invoice["total_amount"])

    return invoice


def parse_white_petal(text: str, run_id: str, doc_id: str, logger: AuditLogger) -> dict:
    invoice = base_schema()

    inv_match = re.search(r"Invoice #\s*(\S+)", text)
    invoice["invoice_number"] = inv_match.group(1) if inv_match else None
    logger.auto_extract_parser(run_id, doc_id, "invoice_number", invoice["invoice_number"])

    date_match = re.search(r"Date of Issue\s*(\d{4}-\d{2}-\d{2})", text)
    invoice["invoice_date"] = date_match.group(1) if date_match else None
    logger.auto_extract_parser(run_id, doc_id, "invoice_date", invoice["invoice_date"])

    due_match = re.search(r"Due Date\s*(\d{4}-\d{2}-\d{2})", text)
    invoice["due_date"] = due_match.group(1) if due_match else None
    logger.auto_extract_parser(run_id, doc_id, "due_date", invoice["due_date"])

    patient_match = re.search(r"BILLED TO:\s*(.+)", text)
    invoice["patient_name"] = patient_match.group(1).strip() if patient_match else None
    logger.auto_extract_parser(run_id, doc_id, "patient_name", invoice["patient_name"])

    address_lines = re.findall(r"BILLED TO:.*\n(.+)\n(.+)\n", text)
    if address_lines:
        invoice["patient_address"] = " ".join([line.strip() for line in address_lines[0]])
    logger.auto_extract_parser(run_id, doc_id, "patient_address", invoice["patient_address"])

    line_items = []
    items_section = re.search(r"CODE DESCRIPTION AMOUNT(.*?)(?:Subtotal|Discount|TOTAL)", text, re.S)
    if items_section:
        for line in items_section.group(1).splitlines():
            m = re.match(r"([A-Z0-9]+)\s+(.+?)\s+\$([\d,]+\.\d{2})", line.strip())
            if m:
                code, desc, amt = m.groups()
                line_items.append({
                    "code": code.strip(),
                    "description": desc.strip(),
                    "amount": float(amt.replace(",", ""))
                })
    invoice["line_items"] = line_items
    logger.auto_extract_parser(run_id, doc_id, "line_items", len(line_items))

    subtotal = re.search(r"Subtotal\s*\$([\d,]+\.\d{2})", text)
    invoice["subtotal_amount"] = float(subtotal.group(1).replace(",", "")) if subtotal else None
    logger.auto_extract_parser(run_id, doc_id, "subtotal_amount", invoice["subtotal_amount"])

    discount = re.search(r"Discount\s*\$([\d,]+\.\d{2})", text)
    invoice["discount_amount"] = float(discount.group(1).replace(",", "")) if discount else None
    logger.auto_extract_parser(run_id, doc_id, "discount_amount", invoice["discount_amount"])

    total = re.search(r"TOTAL\s*\$([\d,]+\.\d{2})", text)
    invoice["total_amount"] = float(total.group(1).replace(",", "")) if total else None
    logger.auto_extract_parser(run_id, doc_id, "total_amount", invoice["total_amount"])

    # provider_name intentionally left None in schema
    return invoice


# -----------------------------
# MAIN PARSING LOOP
# -----------------------------
for filename in os.listdir(input_folder):
    if not filename.endswith(".txt"):
        continue

    path = os.path.join(input_folder, filename)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    run_id = str(uuid.uuid4())
    doc_id = os.path.splitext(filename)[0]

    # Grab detection info from earlier (if we have it)
    detection_info = template_detection_results.get(doc_id, None)

    invoice_logger.parse_start(
        run_id,
        doc_id,
        meta={
            "stage": "invoice_parsing",
            "layout_template_detection": detection_info,
        },
    )

    if "HOT SPRINGS GENERAL" in text:
        template = "hot_springs"
        parsed = parse_hot_springs(text, run_id, doc_id, invoice_logger)
    elif "ROSE PETAL CLINIC" in text:
        template = "rose_petal"
        parsed = parse_rose_petal(text, run_id, doc_id, invoice_logger)
    elif "WHITE PETAL HOSPITAL" in text.upper():
        template = "white_petal"
        parsed = parse_white_petal(text, run_id, doc_id, invoice_logger)
    else:
        template = "unknown"
        parsed = base_schema()
        parsed["error"] = "Unknown template"

    invoice_logger.parse_end(
        run_id=run_id,
        doc_id=doc_id,
        fields_extracted_count=_count_non_null(parsed),
        required_total=None,
        status="success",
        meta={
            "stage": "end_parsing",
            "template": template,
            "layout_template_detection": detection_info,
        },
    )

    cleaned = remove_nulls(parsed)

    out_path = os.path.join(output_folder, f"{doc_id}_{template}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2)

    print(f"✅ Parsed {filename} as {template} → {out_path}")

print("All invoices processed.")
