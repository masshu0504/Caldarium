from pathlib import Path
import re
import pdfplumber
from pdfminer.high_level import extract_text

FIELD_PATTERNS = {
    "invoice_id": re.compile(r"(invoice\s*id|invoice\s*#|inv\s*id|invoice\s*no\.?)[:\s]*([A-Za-z0-9\-]+)", re.IGNORECASE),
    "patient_id": re.compile(r"(patient\s*id|pt\s*id)[:\s]*([A-Za-z0-9\-]+)", re.IGNORECASE),
    "total_amount": re.compile(r"(total\s*(amount)?|amount\s*due)[:\s]*\$?\s*([0-9]+(?:\.[0-9]{2})?)", re.IGNORECASE)
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
    out = {"invoice_id": None, "patient_id": None, "total_amount": None}
    for key, pat in FIELD_PATTERNS.items():
        m = pat.search(text or "")
        if not m:
            continue
        val = m.group(m.lastindex) if m.lastindex else m.group(0)
        out[key] = float(val) if key == "total_amount" else val.strip()
    return out
