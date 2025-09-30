import pdfplumber
import re
import json

# --- CONFIGURATION ---
# Define the path to your sample PDF. This is the file path inside the Docker container.
PDF_PATH = r'minio_buckets/invoices/invoice_T1_gen1.pdf'

# --- REGEX PATTERNS ---
# We use raw strings (r'') for regex to prevent Python from interpreting backslashes.

# 1. Invoice ID: Targets the specific format INV followed by 6 digits (e.g., INV377776)
INVOICE_ID_PATTERN = r'Invoice #\s*(INV\d+)'

# 2. Patient ID: Targets the MRN format (e.g., MRN53310). 
# We look for the label "MRN" followed by 5 or more digits.
PATIENT_ID_PATTERN = r'\s(MRN\d+)'

# 3. Date: Targets the YYYY-MM-DD format (e.g., 2020-03-30) 
# Note: We capture the *first* date following "Date:".
DATE_PATTERN = r'Date:\s*(\d{4}-\d{2}-\d{2})'


def parse_invoice(raw_text):
    """
    Applies regex patterns to extract key fields from the raw text.
    """
    
    data = {
        "invoice_id": None,
        "patient_id": None,
        "date": None
    }
    
    # 1. Capture Invoice ID
    match = re.search(INVOICE_ID_PATTERN, raw_text)
    if match:
        # The capture group (1) holds the INV377776 part
        data['invoice_id'] = match.group(1)
        
    # 2. Capture Date
    match = re.search(DATE_PATTERN, raw_text)
    if match:
        # The capture group (1) holds the 2020-03-30 part
        data['date'] = match.group(1)
        
    # 3. Capture Patient ID (MRN)
    match = re.search(PATIENT_ID_PATTERN, raw_text)
    if match:
        # The capture group (1) holds the MRN53310 part
        data['patient_id'] = match.group(1).strip()
        
    return data

def main():
    """Main function to run the extraction and parsing process."""
    try:
        with pdfplumber.open(PDF_PATH) as pdf:
            # Extract text from the first page
            raw_text = pdf.pages[0].extract_text()

            if raw_text:
                # Parse the key fields
                extracted_data = parse_invoice(raw_text)
                
                # Output the results in a clear, formatted way (JSON is good for engineers!)
                print(json.dumps(extracted_data, indent=4))
                
            else:
                print(f"Error: Could not extract text from {PDF_PATH}.")
    
    except FileNotFoundError:
        print(f"CRITICAL ERROR: The PDF file at {PDF_PATH} was not found.")
    except IndexError:
        print(f"CRITICAL ERROR: The PDF at {PDF_PATH} appears to be empty or has no pages.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
