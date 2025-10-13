import pdfplumber
import re
import json
from io import BytesIO

# --- REVISED REGEX PATTERNS (Accounting for table-induced whitespace/newlines) ---

FIELD_PATTERNS = {
    # 1. Invoice & Account IDs
    "invoice_number": re.compile(r"Invoice\s*#\s*(\w+)", re.IGNORECASE),
    # CHANGED: Replaced patient_id with account_number (MRN is under Account No. label in PDF)
    "account_number": re.compile(r"Account\s*No[\s\n]*(\w+)", re.IGNORECASE), 

    # 2. Dates (Using very loose whitespace to bridge label and value across columns/lines)
    # The structure in the raw text often looks like: 'Date:      2020-03-30'
    "invoice_date": re.compile(r"Date:\s*(\d{4}-\d{2}-\d{2})"),
    # FIXED: Added more flexibility for Due Date capture
    "due_date": re.compile(r"Due\s*Date[\s\n]+(\d{4}-\d{2}-\d{2})", re.IGNORECASE), 
    
    "admission_date": re.compile(r"Admission\s*Date:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE),
    "discharge_date": re.compile(r"Discharge\s*Date:\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE),

    # 3. Patient Information (Need precise capturing boundaries)
    # Name: Captures text after "Patient Name:", stopping at the next label ("Hospital No")
    "patient_name": re.compile(r"Patient\s*Name:\s*([A-Za-z\s]+?)(Hospital\s*No)", re.IGNORECASE),
    "patient_age": re.compile(r"Patient\s*Age:\s*(\d+)", re.IGNORECASE),
    
    # Address: Capture everything between Address: and the next label (Admission Date)
    "patient_address": re.compile(r"Address:\s*([\s\S]*?)Admission\s*Date:", re.IGNORECASE),

    # 4. Financial Totals (Must ensure we capture numbers with optional commas/decimals)
    "subtotal_amount": re.compile(r"Sub\s*Total\s*\$?([\d,]+(?:\.\d{2})?)", re.IGNORECASE | re.DOTALL),
    "discount_amount": re.compile(r"Discount\s*\$?([\d,]+(?:\.\d{2})?)", re.IGNORECASE | re.DOTALL),
    "total_amount": re.compile(r"Total\s*\$?([\d,]+(?:\.\d{2}))", re.IGNORECASE | re.DOTALL),
}


def clean_and_convert(key, value):
    """Cleans extracted values and converts them to the correct data type."""
    if value is None:
        return None
    
    # Clean up value: remove newlines, multiple spaces, and commas
    cleaned_value = re.sub(r'\s+', ' ', value).strip().replace(',', '')
    
    # Numeric conversions
    if key in ["subtotal_amount", "discount_amount", "total_amount", "amount", "patient_age"]:
        try:
            # Handle float/int conversion
            if key == "patient_age":
                return int(float(cleaned_value)) 
            else:
                return float(cleaned_value)
        except ValueError:
            return None
    
    # Specific cleanup for fields like patient_name 
    if key == "patient_name":
        # Final trim after capturing up to 'Hospital No'
        return cleaned_value.replace("Hospital No", "").strip()
        
    if key == "patient_address":
        # Remove the Admission Date label text and clean up whitespace
        return cleaned_value.replace("Admission Date:", "").strip()

    return cleaned_value.strip()


def parse_invoice(raw_text, pdf_pages):
    """
    Applies regex patterns to extract key header/footer fields and uses 
    column parsing for line items.
    """
    data = {
        "account_number": None # New required field
    }
    
    # 1. Extract Header and Footer Fields
    for key, pattern in FIELD_PATTERNS.items():
        # Apply DOTALL if needed for multi-line block capture
        flags = re.IGNORECASE | (re.DOTALL if "[\s\S]*?" in pattern.pattern else 0)
        match = pattern.search(raw_text, flags)
        
        if match:
            # Most new patterns use group(1) or group(2) for the value
            # We now safely check all available groups, prioritizing the value
            raw_value = match.group(match.lastindex) if match.lastindex else match.group(0)
            data[key] = clean_and_convert(key, raw_value)
        else:
            data[key] = None

    # 2. Extract Line Items (Keep this section robust)
    try:
        table_settings = {
            "vertical_strategy": "lines", 
            "horizontal_strategy": "lines",
        }
        
        tables = pdf_pages[0].extract_tables(table_settings)
        line_items = []
        
        for table in tables:
            if table and len(table) > 1 and table[0][0] and table[0][0].strip().lower() == 'code':
                for row in table[1:]:
                    if len(row) >= 3 and row[1] and row[2]: 
                        item = {
                            "code": row[0].strip() if row[0] else None,
                            "description": row[1].strip(),
                            "amount": clean_and_convert("amount", row[2]) 
                        }
                        if item['amount'] is not None:
                             line_items.append(item)
                
        data['line_items'] = line_items
            
    except Exception as e:
        print(f"Warning: Line item extraction failed: {e}")
        data['line_items'] = []

    # 3. Final cleanup for multi-line address capture (Must run after regex)
    if 'patient_address' in data and data['patient_address']:
        # Remove extra text from the address that regex over-captured
        data['patient_address'] = re.sub(r'\s+', ' ', data['patient_address']).strip()
        
    # Remove the unwanted patient_id field
    if 'patient_id' in data:
        del data['patient_id']

    return data


def parse_pdf_bytes(pdf_bytes: bytes) -> dict:
    """Wrapper function to open the PDF bytes and execute the core parsing logic."""
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages:
                 return {"error": "The uploaded PDF appears to be empty."}

            raw_text = pdf.pages[0].extract_text() 
            pdf_pages = pdf.pages 
            
            if raw_text:
                return parse_invoice(raw_text, pdf_pages)
            else:
                return {"error": "Could not extract text from PDF."}
    
    except Exception as e:
        print(f"CRITICAL PARSING ERROR: {e}") 
        return {"error": f"An unexpected error occurred during PDF processing: {e}"}