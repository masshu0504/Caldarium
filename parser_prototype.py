import pdfplumber, re, json
from io import BytesIO

def normalize_to_invoice_schema_v1(data: dict) -> dict:
    out = dict(data) if data else {}

    # account_number -> patient_id
    if 'patient_id' not in out and out.get('account_number'):
        out['patient_id'] = out.pop('account_number')
    else:
        out.pop('account_number', None)

    # remove deprecated field
    out.pop('tax_percent', None)

    # ensure nullable fields exist
    out.setdefault('provider_name', None)
    out.setdefault('bed_id', None)

    return out

# ---------- Preprocessing ----------
LABEL_NORMALIZATIONS = [
    (r"Due\s+Date", "Due Date"),
    (r"Account\s*No\.?", "Account No"),
    (r"Invoice\s*#", "Invoice #"),
    (r"Patient\s*Name\s*:", "Patient Name:"),
    (r"Hospital\s*No\s*:", "Hospital No:"),
    (r"Patient\s*Age\s*:", "Patient Age:"),
    (r"Admission\s*Date\s*:", "Admission Date:"),
    (r"Discharge\s*Date\s*:", "Discharge Date:"),
    (r"Sub\s*Total", "Sub Total"),
    (r"Bed\s*No\s*:", "Bed No:"),
]

def preprocess_text(raw: str) -> str:
    if not raw:
        return raw
    txt = raw.replace("\r", "\n")
    txt = re.sub(r"\$\s*\n\s*", "$", txt)
    txt = re.sub(r"(Due)\s*\n\s*(Date)", r"\1 \2", txt, flags=re.IGNORECASE)
    txt = re.sub(r"(Account)\s*\n\s*(No\.?)", r"\1 \2", txt, flags=re.IGNORECASE)
    txt = re.sub(r"(Invoice)\s*\n\s*(#)", r"\1 \2", txt, flags=re.IGNORECASE)
    for pat, rep in LABEL_NORMALIZATIONS:
        txt = re.sub(pat, rep, txt, flags=re.IGNORECASE)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    sentinel = " \u2028 "
    txt = txt.replace("\n", sentinel)
    txt = re.sub(r"[ \t]{2,}", " ", txt)
    txt = txt.replace(sentinel, "\n")
    txt = "\n".join(line.strip() for line in txt.splitlines())
    return txt

# ---------- Regex patterns ----------
FIELD_PATTERNS = {
    # IDs
    "invoice_number": re.compile(r"Invoice\s*#\s*([A-Z0-9-]+)", re.IGNORECASE),
    "account_number": re.compile(r"Account\s*No\.?\s*([A-Z0-9-]+)", re.IGNORECASE),

    # Dates
    # accept "Invoice Date: 2020-03-30" or "Date: 2020-03-30"
    "invoice_date": re.compile(r"(?:Invoice\s*Date|Date):\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE),
    "due_date": re.compile(r"Due\s*Date\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE),
    "admission_date": re.compile(r"Admission\s*Date:\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE),
    "discharge_date": re.compile(r"Discharge\s*Date:\s*(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE),

    # Patient info
    "patient_name": re.compile(
        r"Patient\s*Name:\s*([A-Za-z][A-Za-z\s'.-]+?)(?:\s*Hospital\s*No:|\n[A-Z][a-z]+[:])",
        re.IGNORECASE
    ),
    "patient_age": re.compile(r"Patient\s*Age:\s*(\d+)\b", re.IGNORECASE),
    "patient_address": re.compile(
        r"Address:\s*(.+?)\s*Admission\s*Date:",
        re.IGNORECASE | re.DOTALL
    ),

    # Financials
    "subtotal_amount": re.compile(r"Sub\s*Total\s*\$?([\d,]+(?:\.\d{2})?)", re.IGNORECASE),
    "discount_amount": re.compile(r"Discount\s*\$?([\d,]+(?:\.\d{2})?)", re.IGNORECASE),
    # IMPORTANT: anchor 'Total' to start of line so it doesn't match "Sub Total"
    "total_amount": re.compile(r"^\s*Total\b\s*\$?([\d,]+(?:\.\d{2})?)", re.IGNORECASE | re.MULTILINE),
    # no tax_percent on purpose
}

def clean_and_convert(key, value):
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip().replace(",", "")
    if key in {"subtotal_amount","discount_amount","total_amount","amount"}:
        try:
            return float(cleaned)
        except ValueError:
            return None
    if key == "patient_age":
        try:
            return int(float(cleaned))
        except ValueError:
            return None
    return cleaned

def extract_fields(prepped_text: str) -> dict:
    data = {}
    for key, pat in FIELD_PATTERNS.items():
        m = pat.search(prepped_text)
        data[key] = clean_and_convert(key, m.group(1)) if m else None
    return data

def extract_line_items(first_page) -> list:
    items = []
    try:
        tables = first_page.extract_tables(
            table_settings={"vertical_strategy": "lines", "horizontal_strategy": "lines"}
        )
        for table in tables or []:
            if table and any("code" in (c or "").strip().lower() for c in table[0]):
                for row in table[1:]:
                    if not row or len(row) < 3:
                        continue
                    code = (row[0] or "").strip() or None
                    desc = (row[1] or "").strip() or None
                    amt = clean_and_convert("amount", (row[2] or "").strip().replace("$",""))
                    if desc and amt is not None:
                        items.append({"code": code, "description": desc, "amount": amt})
    except Exception:
        pass

    if not items:
        txt = first_page.extract_text() or ""
        pre = preprocess_text(txt)
        for m in re.finditer(r"^([A-Z0-9]{2,})\s+(.+?)\s+\$?([\d,]+\.\d{2})$", pre, flags=re.MULTILINE):
            code, desc, amt = m.groups()
            items.append({"code": code.strip(), "description": desc.strip(),
                          "amount": clean_and_convert("amount", amt)})
    return items

def parse_invoice(prepped_text: str, page) -> dict:
    data = extract_fields(prepped_text)

    # account_number fallback (MRN##### in free text)
    if not data.get("account_number"):
        m = re.search(r"\bMRN[0-9]+\b", prepped_text)
        if m:
            data["account_number"] = m.group(0)

    # due_date fallback: second ISO date near header
    if not data.get("due_date"):
        lines = prepped_text.splitlines()
        header = []
        for line in lines:
            header.append(line)
            if "Patient Details" in line:
                break
        dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", "\n".join(header))
        inv = data.get("invoice_date")
        if inv and inv in dates and len(dates) > 1:
            data["due_date"] = next((d for d in dates if d != inv), None)
        elif len(dates) >= 2:
            data["due_date"] = dates[1]

    # patient_address fallback
    if not data.get("patient_address"):
        lines = prepped_text.splitlines()
        for i, line in enumerate(lines):
            if re.search(r"\bAddress:", line):
                parts = []
                if i-1 >= 0 and (":" not in lines[i-1]):
                    parts.append(lines[i-1].strip())
                for j in (1, 2):
                    if i+j < len(lines):
                        nxt = lines[i+j].strip()
                        if re.search(r"\b[A-Z]{2}\s*\d{5}\b", nxt) or (":" not in nxt):
                            parts.append(nxt)
                data["patient_address"] = (" ".join(p for p in parts if p).strip()) or None
                break

    data["line_items"] = extract_line_items(page)
    return data

def parse_pdf_bytes(pdf_bytes: bytes) -> dict:
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            page = pdf.pages[0]
            raw_text = page.extract_text()
            if not raw_text:
                return {"error": "Could not extract text from PDF."}

            prepped = preprocess_text(raw_text)
            parsed = parse_invoice(prepped, page)
            return normalize_to_invoice_schema_v1(parsed)

    except Exception as e:
        return {"error": f"An unexpected error occurred during PDF processing: {e}"}
