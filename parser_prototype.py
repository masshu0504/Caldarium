import pdfplumber, re, json
from io import BytesIO

# ---------- Preprocessing helpers ----------
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
    """Make scattered PDF text more regex-friendly."""
    if not raw: return raw
    txt = raw.replace("\r", "\n")

    # Fuse broken money tokens like "$\n430.00"
    txt = re.sub(r"\$\s*\n\s*", "$", txt)

    # Fuse split label tokens caused by column breaks
    txt = re.sub(r"(Due)\s*\n\s*(Date)", r"\1 \2", txt, flags=re.IGNORECASE)
    txt = re.sub(r"(Account)\s*\n\s*(No\.?)", r"\1 \2", txt, flags=re.IGNORECASE)
    txt = re.sub(r"(Invoice)\s*\n\s*(#)", r"\1 \2", txt, flags=re.IGNORECASE)

    # Normalize common label variants
    for pat, rep in LABEL_NORMALIZATIONS:
        txt = re.sub(pat, rep, txt, flags=re.IGNORECASE)

    # Tidy whitespace (keep single newlines as soft separators)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    sentinel = " \u2028 "
    txt = txt.replace("\n", sentinel)
    txt = re.sub(r"[ \t]{2,}", " ", txt)
    txt = txt.replace(sentinel, "\n")
    txt = "\n".join(line.strip() for line in txt.splitlines())
    return txt

# ---------- Regex patterns (compiled once) ----------
FIELD_PATTERNS = {
    # IDs
    "invoice_number": re.compile(r"Invoice\s*#\s*([A-Z0-9-]+)", re.IGNORECASE),
    "account_number": re.compile(r"Account\s*No\.?\s*([A-Z0-9-]+)", re.IGNORECASE),

    # Dates
    "invoice_date": re.compile(r"\bDate:\s*(\d{4}-\d{2}-\d{2})\b"),
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
    "tax_percent": re.compile(r"Tax:\s*([\d.]+)%", re.IGNORECASE),
    # IMPORTANT: anchor 'Total' to start of line so it doesn't match "Sub Total"
    "total_amount": re.compile(r"^\s*Total\b\s*\$?([\d,]+(?:\.\d{2})?)", re.IGNORECASE | re.MULTILINE),
}

def clean_and_convert(key, value):
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip().replace(",", "")
    if key in {"subtotal_amount","discount_amount","total_amount","amount"}:
        try: return float(cleaned)
        except ValueError: return None
    if key == "patient_age":
        try: return int(float(cleaned))
        except ValueError: return None
    return cleaned

def extract_fields(prepped_text: str) -> dict:
    data = {}
    for key, pat in FIELD_PATTERNS.items():
        m = pat.search(prepped_text)
        data[key] = clean_and_convert(key, m.group(1)) if m else None
    return data

def extract_line_items(first_page) -> list:
    """Prefer table extraction; fall back to text lines."""
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

    # --- Fallbacks for tricky layouts ---
    # account_number: allow standalone MRN*
    if not data.get("account_number"):
        m = re.search(r"\bMRN[0-9]+\b", prepped_text)
        if m: data["account_number"] = m.group(0)

    # due_date: often the second ISO date in the Invoice Details block
    if not data.get("due_date"):
        block = []
        for line in prepped_text.splitlines():
            block.append(line)
            if "Patient Details" in line:
                break
        dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", "\n".join(block))
        inv = data.get("invoice_date")
        if inv and inv in dates and len(dates) > 1:
            for d in dates:
                if d != inv:
                    data["due_date"] = d
                    break
        elif len(dates) >= 2:
            data["due_date"] = dates[1]

    # patient_address: if regex failed, stitch prev/next lines around 'Address:'
    if not data.get("patient_address"):
        lines = prepped_text.splitlines()
        for i, line in enumerate(lines):
            if re.search(r"\bAddress:", line):
                parts = []
                # previous line may contain street
                if i-1 >= 0 and (":" not in lines[i-1]):
                    parts.append(lines[i-1].strip())
                # collect next couple lines if they look like address/city-state-zip or not labels
                for j in (1, 2):
                    if i+j < len(lines):
                        nxt = lines[i+j].strip()
                        if re.search(r"\b[A-Z]{2}\s*\d{5}\b", nxt) or (":" not in nxt):
                            parts.append(nxt)
                stitched = " ".join(p for p in parts if p).strip()
                data["patient_address"] = stitched or None
                break

    # line items
    data["line_items"] = extract_line_items(page)
    return data

def parse_pdf_bytes(pdf_bytes: bytes) -> dict:
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages:
                return {"error": "The uploaded PDF appears to be empty."}
            raw_text = pdf.pages[0].extract_text()
            if not raw_text:
                return {"error": "Could not extract text from PDF."}
            prepped = preprocess_text(raw_text)
            return parse_invoice(prepped, pdf.pages[0])
    except Exception as e:
        return {"error": f"An unexpected error occurred during PDF processing: {e}"}
