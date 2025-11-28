import re
from typing import Dict, Any, Union
# Import pdfplumber for PDF text extraction
import pdfplumber 
import io # Added for handling binary data stream

# Define the expected output structure based on the provided JSON schema.
# Note: In a production environment, you would use Pydantic for schema enforcement.
ConsentData = Dict[str, Union[str, None]]

# --- Template Detection Heuristics ---
TEMPLATE_1_IDENTIFIER = "The Occupational Medical Service will only utilize a signed"
TEMPLATE_2_IDENTIFIER = "HIPAA Authorization Form"

# --- Helper Function to Extract Value Safely ---
def extract_field(text: str, pattern: str, default: str = None) -> Union[str, None]:
    """Helper function to run regex and return a cleaned string or None."""
    # Use re.MULTILINE to handle start-of-line anchors if needed, and re.DOTALL 
    # for multiline matching across the full document text.
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
    if match and match.groups():
        return match.group(1).strip()
    return default

# --- Template 1 Parser (Based on Images {514EE936-7E89-4DC7-9B2E-D6D0CB164DF2}.png & {2182E1D1-FFA9-4FE4-B013-7113DCC7ED62}.png) ---
def parse_template_1(text_content: str) -> ConsentData:
    """Parses data from Template 1 (Occupational Medical Service Authorization)."""
    
    # Initialize all fields to None
    data: ConsentData = {
        # Patient Info
        "patient_name": None, "patient_first_name": None, "patient_middle_name": None, "patient_last_name": None,
        "patient_address_name": None, "patient_id": None, "patient_dob": None,
        "patient_signature": None, "patient_state": None, "patient_city": None, "patient_zip_code": None,
        # Provider Info
        "provider_name": None, "provider_address_name": None, "provider_phone": None, "provider_fax": None,
        "provider_state": None, "provider_city": None, "provider_zip_code": None,
        # Family/Guardian Info
        "family_name": None, "family_relation": None, "family_phone": None, "family_address_name": None,
        "family_state": None, "family_city": None, "family_zip_code": None,
        "guardian_name": None, "guardian_signature": None, "guardian_relation": None,
        # Dates
        "date": None, "expiration_date": None, "expiration_event": None,
        # Translator
        "translator_name": None, "translator_signature": None,
    }
    
    # --- Patient Fields ---
    # Based on "5. PRINT NAME OF PATIENT Courtney Wilcox"
    data["patient_name"] = extract_field(text_content, r"5\.\s*PRINT\s*NAME\s*OF\s*PATIENT\s*(\w+\s*\w+)")
    data["patient_signature"] = extract_field(text_content, r"7\.\s*SIGNATURE\s*OF\s*PATIENT\s*(\w+\s*\w+)")
    # For splitting the name, further NLP or regex refinement would be needed. Assuming simple split here:
    if data["patient_name"]:
        parts = data["patient_name"].split()
        data["patient_first_name"] = parts[0]
        data["patient_last_name"] = parts[-1]

    # --- Provider Fields (TREATING MEDICAL CARE PROVIDER) ---
    # Based on NAME Dr. Steven Walker PHONE 406-647-6837
    # Adjusting regex to be more robust to spacing and newline issues based on image text layout
    # The text from the PDF is structured with quoted fields, which affects text parsing.
    # Reverting to simpler regex as the text content from the PDF appears to strip out the quotes but still contains the keywords.

    # Finding NAME, PHONE, FAX
    data["provider_name"] = extract_field(text_content, r"NAME\s+([^\n]+?)\s+PHONE", re.MULTILINE)
    # The phone/fax extraction needs to handle the possibility of extra text/newlines after the label.
    data["provider_phone"] = extract_field(text_content, r"PHONE\s+([\d\s\-\(\)]+)", re.MULTILINE)
    data["provider_fax"] = extract_field(text_content, r"FAX\s+([\d\s\-\(\)]+)", re.MULTILINE)
    
    # Finding ADDRESS
    data["provider_address_name"] = extract_field(text_content, r"ADDRESS\s+([^\n]+?)CITY", re.MULTILINE)
    data["provider_city"] = extract_field(text_content, r"CITY\s+([^\n]+?)STATE", re.MULTILINE)
    data["provider_state"] = extract_field(text_content, r"STATE\s+([^\n]+?)ZIP", re.MULTILINE)
    data["provider_zip_code"] = extract_field(text_content, r"ZIP\s+(\d+)", re.MULTILINE)

    # --- Date Fields ---
    # Based on "9. DATE OF SIGNATURE 2025-10-27"
    data["date"] = extract_field(text_content, r"9\.\s*DATE\s*OF\s*SIGNATURE\s*(\d{4}-\d{2}-\d{2})")
    
    # Based on "TO 2026-10-27" in Box 4
    data["expiration_date"] = extract_field(text_content, r"TO\s*(\d{4}-\d{2}-\d{2})")
    
    # Based on "period of six months from date of signature." (Alternative expiration event)
    data["expiration_event"] = "Six months from date of signature"

    # --- Guardian Fields ---
    # Extract the data under "8. SIGNATURE OF PARENT/GUARDIAN/POWER OF ATTORNEY"
    guardian_sig_data = extract_field(text_content, r"8\.\s*SIGNATURE\s*OF\s*PARENT/GUARDIAN/POWER\s*OF\s*ATTORNEY\s+([^\n]+)")
    if guardian_sig_data and guardian_sig_data.strip().upper() != "N/A":
        data["guardian_signature"] = guardian_sig_data.strip()
    
    return data


# --- Template 2 Parser (Based on Images {843D8E8C-8D7E-4252-AFA7-878587F086F5}.png & {8D91A13D-9D0B-439A-88A7-D4991DBC9373}.png) ---
def parse_template_2(text_content: str) -> ConsentData:
    """Parses data from Template 2 (HIPAA Authorization Form)."""
    
    data: ConsentData = {
        # Patient Info
        "patient_name": None, "patient_first_name": None, "patient_middle_name": None, "patient_last_name": None,
        "patient_address_name": None, "patient_id": None, "patient_dob": None,
        "patient_signature": None, "patient_state": None, "patient_city": None, "patient_zip_code": None,
        # Provider Info (Section 2 - Discloser)
        "provider_name": None, "provider_address_name": None, "provider_phone": None, "provider_fax": None,
        "provider_state": None, "provider_city": None, "provider_zip_code": None,
        # Family/Guardian Info (Section 3 - Receiver)
        "family_name": None, "family_relation": None, "family_phone": None, "family_address_name": None,
        "family_state": None, "family_city": None, "family_zip_code": None,
        "guardian_name": None, "guardian_signature": None, "guardian_relation": None,
        # Dates
        "date": None, "expiration_date": None, "expiration_event": None,
        # Translator
        "translator_name": None, "translator_signature": None,
    }
    
    # Helper to grab content between Section X and Section Y
    def get_section_text(start_section: int, end_section: int, text: str) -> str:
        # Adjusted pattern to capture all content between two section headers
        pattern = rf"(Section\s*{start_section}\s*-\s*.*?)(?=Section\s*{end_section}\s*-)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        # If the end section is not found (e.g., the last section), return everything until the end
        if match:
            return match.group(1)
        
        # Special case: try to grab content from the start section until the very end
        if end_section > 4: # Assuming sections 4 and below are well-defined
            # Attempt to capture from start_section to the end of the text
            pattern_end = rf"(Section\s*{start_section}\s*-\s*.*)"
            match_end = re.search(pattern_end, text, re.DOTALL | re.IGNORECASE)
            return match_end.group(1) if match_end else ""
        
        return ""

    sec1_text = get_section_text(1, 2, text_content)
    sec2_text = get_section_text(2, 3, text_content)
    sec3_text = get_section_text(3, 4, text_content)
    sec4_text = get_section_text(4, 5, text_content) 
    sec6_text = get_section_text(6, 7, text_content) 

    # --- Patient Fields (Section 1) ---
    data["patient_first_name"] = extract_field(sec1_text, r"First\s*Name:\s*([^\n]+)")
    data["patient_last_name"] = extract_field(sec1_text, r"Last\s*Name:\s*([^\n]+)")
    data["patient_middle_name"] = extract_field(sec1_text, r"Middle\s*Name:\s*([^\n]+)")
    
    # Clean up "N/A" entries
    if data["patient_middle_name"] and data["patient_middle_name"].strip().upper() == 'N/A':
        data["patient_middle_name"] = None
        
    data["patient_dob"] = extract_field(sec1_text, r"Date\s*of\s*Birth:\s*([^\n]+)")
    # Assume patient_id is the Reference No. MRN7994
    data["patient_id"] = extract_field(sec1_text, r"Reference\s*N°:\s*([^\n]+)")
    data["patient_address_name"] = extract_field(sec1_text, r"Address:\s*([^\n]+)")
    
    # Extract City/State/ZIP from combined field: Leeland/Montana/14249
    city_state_zip = extract_field(sec1_text, r"City/State/ZIP:\s*([^\n]+)")
    if city_state_zip and '/' in city_state_zip:
        parts = city_state_zip.split('/')
        if len(parts) == 3:
            data["patient_city"] = parts[0].strip()
            data["patient_state"] = parts[1].strip()
            data["patient_zip_code"] = parts[2].strip()
            
    # Assemble full name
    data["patient_name"] = " ".join(filter(None, [data["patient_first_name"], data["patient_last_name"]]))

    # Signature/Date (Based on first entry in Section 6 signatures/dates, assuming this is the patient)
    # Target: Signature: Courtney Thomas Date: 2025-10-27 (the first signature line)
    sig_match = re.search(r"Signature:\s*([^\s]+?)\s*([^\s]+?)\s*Date:\s*(\d{4}-\d{2}-\d{2})", sec6_text, re.DOTALL)
    if sig_match:
        data["patient_signature"] = f"{sig_match.group(1)} {sig_match.group(2)}"
        data["date"] = sig_match.group(3)
    
    # --- Provider Fields (Section 2 - Individual/Organization Authorized by Signatory to Disclose PHI) ---
    # The 'Discloser' is treated as the 'Provider'
    data["provider_name"] = extract_field(sec2_text, r"Name:\s*([^\n]+)")
    data["provider_address_name"] = extract_field(sec2_text, r"Address:\s*([^\n]+)")
    # Phone/Fax are not present in this section of the form image
    
    provider_city_state_zip = extract_field(sec2_text, r"City/State/ZIP:\s*([^\n]+)")
    if provider_city_state_zip and '/' in provider_city_state_zip:
        parts = provider_city_state_zip.split('/')
        if len(parts) == 3:
            data["provider_city"] = parts[0].strip()
            data["provider_state"] = parts[1].strip()
            data["provider_zip_code"] = parts[2].strip()

    # --- Family Fields (Section 3 - Individual/Organization Authorized by Signatory to Receive PHI) ---
    # The 'Receiver' is treated as the 'Family/Contact'
    data["family_name"] = extract_field(sec3_text, r"Name:\s*([^\n]+)")
    data["family_relation"] = extract_field(sec3_text, r"Relationship\s*to\s*Patient/Plan\s*Member:\s*([^\n]+)")
    data["family_phone"] = extract_field(sec3_text, r"Telephone\s*N°:\s*([^\n]+)")
    
    # Family Address (reusing logic from patient address since the format is the same)
    data["family_address_name"] = extract_field(sec3_text, r"Address:\s*([^\n]+)")
    
    family_csz = extract_field(sec3_text, r"City/State/ZIP:\s*([^\n]+)")
    if family_csz and '/' in family_csz:
        parts = family_csz.split('/')
        if len(parts) == 3:
            data["family_city"] = parts[0].strip()
            data["family_state"] = parts[1].strip()
            data["family_zip_code"] = parts[2].strip()
                
    # --- Date Fields (Section 4) ---
    data["expiration_event"] = extract_field(sec4_text, r"Expiration\s*Event:\s*([^\n]+)")
    data["expiration_date"] = extract_field(sec4_text, r"Expiration\s*Date:\s*([^\n]+)")
    
    # Clean up fields that might be N/A or empty
    if data["expiration_date"] and data["expiration_date"].strip().upper() == 'N/A':
        data["expiration_date"] = None
    if data["expiration_event"] and data["expiration_event"].strip().upper() == 'N/A':
        data["expiration_event"] = None

    return data


# --- Main Dispatcher Function ---
def parse_consent_pdf_bytes(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Main entry point for parsing consent forms.
    
    This function performs:
    1. Text extraction from the PDF bytes using pdfplumber.
    2. Document template detection based on keywords.
    3. Dispatch to the correct template parsing function.
    """
    
    # 1. Use pdfplumber to extract text from the binary PDF data
    text_content = ""
    try:
        # pdfplumber works best with a file-like object created from bytes
        # Since pdfplumber is confirmed to be in requirements.txt, this is safe.
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                # Add text content, ensuring newlines separate pages
                text_content += page.extract_text(x_tolerance=2) + "\n\n"
        
    except ImportError:
        # This occurs if pdfplumber is not installed (even though it's in the list)
        return {"error": "pdfplumber library not found. Please ensure all Python dependencies are installed correctly."}
    except Exception as e:
        # Catch any actual PDF reading or structure errors
        return {"error": f"Failed to extract text from PDF using pdfplumber: {e}"}

    # Clean up common OCR/parsing artifacts (e.g., multiple spaces, leading/trailing whitespace)
    text_content = re.sub(r'\s{2,}', ' ', text_content).strip()
    
    # --- Template Detection ---
    if TEMPLATE_1_IDENTIFIER in text_content:
        # Template 1 (Occupational Medical Service) detected
        result = parse_template_1(text_content)
        result["template"] = "Template 1 (Occupational Medical Service)"
    elif TEMPLATE_2_IDENTIFIER in text_content:
        # Template 2 (HIPAA Authorization Form) detected
        result = parse_template_2(text_content)
        result["template"] = "Template 2 (HIPAA Authorization Form)"
    else:
        # No known template detected
        return {"error": "Unknown consent form template detected."}

    # --- Final Schema Validation (Optional but Recommended) ---
    required_fields = [
        "patient_name", "patient_signature", "provider_name", 
        "provider_address_name", "provider_city", "provider_state", 
        "provider_zip_code", "date"
    ]
    
    missing_fields = [field for field in required_fields if result.get(field) is None]
    
    if missing_fields:
        print(f"Warning: Missing required fields: {', '.join(missing_fields)}")

    return result
