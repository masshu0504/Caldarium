import pdfplumber
import re
import json
from io import BytesIO # <--- Import this!

# --- REGEX PATTERNS (Keep them the same) ---
INVOICE_ID_PATTERN = r'Invoice #\s*(INV\d+)'
PATIENT_ID_PATTERN = r'\s(MRN\d+)'
DATE_PATTERN = r'Date:\s*(\d{4}-\d{2}-\d{2})'


def parse_invoice(raw_text):
    """Applies regex patterns to extract key fields from the raw text."""
    data = {
        "invoice_id": None,
        "patient_id": None,
        "date": None
    }
    
    # [Your existing regex extraction logic goes here, unchanged]
    match = re.search(INVOICE_ID_PATTERN, raw_text)
    if match:
        data['invoice_id'] = match.group(1)
        
    match = re.search(DATE_PATTERN, raw_text)
    if match:
        data['date'] = match.group(1)
        
    match = re.search(PATIENT_ID_PATTERN, raw_text)
    if match:
        data['patient_id'] = match.group(1).strip()
        
    return data


def parse_pdf_bytes(pdf_bytes: bytes) -> dict: # <--- New main function
    """
    Opens the PDF from a bytes stream and returns the parsed data.
    """
    try:
        # Use BytesIO to treat the raw bytes as a file-like object for pdfplumber
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            # Extract text from the first page
            raw_text = pdf.pages[0].extract_text()

            if raw_text:
                return parse_invoice(raw_text)
            else:
                return {"error": "Could not extract text from PDF."}
    
    except Exception as e:
        return {"error": f"An unexpected error occurred during PDF processing: {e}"}

# Note: You can remove the old main() and __name__ == "__main__" block
# as FastAPI will handle the execution.