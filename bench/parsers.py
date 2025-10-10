from pathlib import Path
import re
import pdfplumber
from pdfminer.high_level import extract_text

# running the comparison again using Minna’s regex (you have the code already, just change the regex used)
FIELD_PATTERNS = {
    "invoice_number": re.compile(r"(invoice\s*id|invoice\s*#|inv\s*id|invoice\s*no\.?)[:\s]*([A-Za-z0-9\-]+)", re.IGNORECASE),
    "patient_id": re.compile(r"(patient\s*id|pt\s*id)[:\s]*([A-Za-z0-9\-]+)", re.IGNORECASE),
    "invoice_date": re.compile(r"(invoice\s*date|date)[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{2}/[0-9]{2}/[0-9]{4})", re.IGNORECASE),
    "subtotal_amount": re.compile(r"(subtotal|sub\s*total)[:\s]*\$?\s*([0-9]+(?:\.[0-9]{2})?)", re.IGNORECASE),
    "total_amount": re.compile(r"(total\s*amount|amount\s*due)[:\s]*\$?\s*([0-9]+(?:\.[0-9]{2})?)", re.IGNORECASE)
}

def parse_with_pdfplumber(pdf_path: Path) -> str:
    text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text.append(page.extract_text() or "")
    return "\n".join(text)

def parse_with_pdfminer(pdf_path: Path) -> str:
    return extract_text(str(pdf_path)) or ""

def extract_fields(text: str):
    out = {"invoice_number": None, "patient_id": None, "invoice_date": None, "subtotal_amount": None, "total_amount": None}
    for key, pat in FIELD_PATTERNS.items():
        m = pat.search(text or "")
        if not m:
            continue
        # Use group 2 for the captured value (all patterns have 2 groups)
        val = m.group(2) if len(m.groups()) >= 2 else m.group(0)
        
        if key in ["subtotal_amount", "total_amount"]:
            out[key] = float(val) if val else None
        else:
            out[key] = val.strip() if val else None
    return out

def extract_line_items(pdf_path: Path):
    line_items = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Example: row = [code, description, amount]
                    try:
                        code, description, amount = row
                        line_items.append({
                            "code": code.strip(),
                            "description": description.strip(),
                            "amount": float(amount.replace("$", "").strip())
                        })
                    except Exception:
                        continue
    return line_items
